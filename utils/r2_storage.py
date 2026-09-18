"""
Standalone Cloudflare R2 (S3-compatible object storage) helper.

This is the one storage utility every module uses — nothing module-specific
lives here beyond its entry in MODULE_RULES. A module that wants to store
images in R2 adds one line to MODULE_RULES, adds its own `<field>_key`
database column(s) to hold the returned key, and calls validate_image /
build_key / save / delete / get_url below. See db/task.py's
InterestGroup.cover_image / api/dashboard/ig/dash_ig_view.py for the
reference usage.
"""

import uuid

import boto3
from PIL import Image
from django.conf import settings

# One entry per module that uploads images. Every module's rules live here,
# in one place — this is the only place that changes when a new module
# starts using R2.
MODULE_RULES = {
    "ig_cover": {"folder": "interest_group/cover", "max_size": 5 * 1024 * 1024},
    "ig_icon": {"folder": "interest_group/icon", "max_size": 5 * 1024 * 1024},
}


def get_r2_client():
    """One boto3 client, pointed at the R2 endpoint instead of AWS."""
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",  # R2 doesn't have real AWS-style regions
    )


def validate_image(file_obj, module):
    """
    Returns an error message string if the file isn't an acceptable image
    for this module, or None if it's fine. Re-checks the actual bytes with
    Pillow rather than trusting the browser's content-type label (which can
    be spoofed).
    """
    rules = MODULE_RULES[module]
    if not file_obj.content_type.startswith("image/"):
        return "Expected an image file"
    if file_obj.size > rules["max_size"]:
        return f"Image must be under {rules['max_size'] // (1024 * 1024)} MB"
    try:
        file_obj.seek(0)
        Image.open(file_obj).verify()
    except Exception:
        return "Invalid or corrupted image file"
    file_obj.seek(0)
    return None


def build_key(module):
    """
    Builds a fresh, random storage key under a module's folder, e.g.
    "interest_group/cover/<uuid>.png". Always random, never reused — a
    record that needs to point at a new image gets a brand new key, and the
    caller is responsible for storing that key (in its own `_key` database
    column) and cleaning up the old key once the new one is confirmed saved.
    """
    rules = MODULE_RULES[module]
    return f"{rules['folder']}/{uuid.uuid4()}.png"


def key_belongs_to_module(key, module):
    """
    True if `key` was actually issued for this module (i.e. it's a key a
    module's own view should accept and attach to one of its records).
    Guards against a client uploading under one module and then handing the
    resulting key to a different module's endpoint.
    """
    rules = MODULE_RULES.get(module)
    return bool(rules) and bool(key) and key.startswith(f"{rules['folder']}/")


def save(key, file_obj):
    """Uploads file_obj to R2 under the exact key given."""
    client = get_r2_client()
    file_obj.seek(0)
    client.upload_fileobj(
        file_obj,
        settings.R2_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": file_obj.content_type},
    )


def delete(key):
    """Deletes an object. Safe to call even if it doesn't exist or key is falsy."""
    if not key:
        return
    client = get_r2_client()
    client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)


def get_url(key):
    """Turns a key into a public, browser-loadable URL."""
    return f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{key}"
