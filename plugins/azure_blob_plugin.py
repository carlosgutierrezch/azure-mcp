from typing import Literal
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from semantic_kernel.functions.kernel_function_decorator import kernel_function


class AzureBlobPlugin:
    """
    read_markdown  ➜ devuelve {'content', 'current_type'}
    write_metadata ➜ actualiza 'file_type' del blob
    """

    def __init__(
        self,
        auth_mode: Literal["sas", "conn_str", "managed_identity"],
        account_url: str | None = None,
        sas_token: str | None = None,
        conn_str: str | None = None,
    ):
        if auth_mode == "sas":
            if not (account_url and sas_token):
                raise ValueError("SAS auth necesita account_url y sas_token")
            self.client = BlobServiceClient(account_url, credential=sas_token)

        elif auth_mode == "conn_str":
            if not conn_str:
                raise ValueError("conn_str auth necesita conn_str")
            self.client = BlobServiceClient.from_connection_string(conn_str)

        elif auth_mode == "managed_identity":
            if not account_url:
                raise ValueError("MI auth necesita account_url")
            cred = DefaultAzureCredential()
            self.client = BlobServiceClient(account_url, credential=cred)

        else:
            raise ValueError("auth_mode inválido")

    # ───────────── funciones expuestas al LLM ─────────────
    @kernel_function(
        name="read_markdown",
        description="Descarga un markdown y devuelve su contenido y file_type actual",
    )
    def read_markdown(self, container: str, blob_name: str) -> dict:
        blob = self.client.get_blob_client(container, blob_name)
        text = blob.download_blob().readall().decode()
        ftype = blob.get_blob_properties().metadata.get("file_type", "unknown")
        return {"content": text, "current_type": ftype}

    @kernel_function(
        name="write_metadata",
        description="Actualiza la metadata file_type de un blob",
    )
    def write_metadata(self, container: str, blob_name: str, new_type: str) -> str:
        blob = self.client.get_blob_client(container, blob_name)
        props = blob.get_blob_properties()
        meta = props.metadata or {}
        meta["file_type"] = new_type
        blob.set_blob_metadata(meta)
        return "blob metadata updated"
