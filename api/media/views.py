from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from utils import r2_storage
from utils.permission import CustomizePermission
from utils.response import CustomResponse


class MediaUploadAPIView(APIView):
    """
    The one upload endpoint every module uses to put a file in Cloudflare
    R2. The caller sends the file by itself here first, gets back a key,
    then sends that key on to whichever module endpoint actually owns the
    record (e.g. POST .../ig/<pk>/cover-image/) — the key is inert until a
    module attaches it to something. See utils/r2_storage.py MODULE_RULES
    for the list of valid `module` values.
    """
    authentication_classes = [CustomizePermission]

    @extend_schema(
        tags=['Media'],
        description="Upload a file to Cloudflare R2. Requires 'file' and 'module' fields.",
    )
    def post(self, request):
        file_obj = request.FILES.get("file")
        module = request.data.get("module")

        if not file_obj:
            return CustomResponse(general_message="No file provided").get_failure_response()
        if not module:
            return CustomResponse(general_message="No module provided").get_failure_response()
        if module not in r2_storage.MODULE_RULES:
            return CustomResponse(
                general_message=f"Unknown module '{module}'"
            ).get_failure_response()

        error = r2_storage.validate_image(file_obj, module)
        if error:
            return CustomResponse(general_message=error).get_failure_response()

        key = r2_storage.build_key(module)
        r2_storage.save(key, file_obj)

        return CustomResponse(
            response={"key": key, "url": r2_storage.get_url(key)}
        ).get_success_response()


class MediaRetrieveAPIView(APIView):
    """
    Turns a previously-issued R2 key back into a public URL. Since the
    bucket is public, this is a convenience lookup for a client that only
    has a key on hand (e.g. read back from a database field) and doesn't
    want to hardcode the R2 public domain itself — it does not check the
    object actually exists (module tables are the source of truth for that,
    via their own `_key` columns).
    """

    @extend_schema(
        tags=['Media'],
        description="Resolve a previously-issued R2 key to its public URL.",
    )
    def get(self, request, key):
        return CustomResponse(
            response={"key": key, "url": r2_storage.get_url(key)}
        ).get_success_response()
