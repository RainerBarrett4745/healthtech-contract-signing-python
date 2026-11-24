import json
import os
import base64
from dataclasses import dataclass

from src.infrai_client import InfraiClient


@dataclass(frozen=True)
class AppointmentContract:
    appointment_id: str
    patient_id: str
    consent_state: str
    pdf: bytes
    cert_pem: str
    key_pem: str


def sign_contract(contract: AppointmentContract, client: InfraiClient, bucket: str = "health-contracts") -> dict[str, str]:
    if contract.consent_state != "completed":
        return {"appointment_id": contract.appointment_id, "state": "blocked"}
    signed_pdf = client.sign(contract.pdf, contract.cert_pem, contract.key_pem)
    object_key = f"appointments/{contract.patient_id}/{contract.appointment_id}.pdf"
    client.put_object(bucket, object_key, signed_pdf)
    return {
        "appointment_id": contract.appointment_id,
        "state": "ready",
        "download_url": client.signed_download(bucket, object_key),
    }


def main() -> None:
    client = InfraiClient()
    bucket = os.environ.get("INFRAI_BUCKET", "health-contracts")
    pdf_path = os.environ.get("PDF_PATH")
    pdf_base64 = os.environ.get("PDF_BASE64")
    if pdf_path:
        with open(pdf_path, "rb") as pdf_file:
            pdf = pdf_file.read()
    elif pdf_base64:
        pdf = base64.b64decode(pdf_base64)
    else:
        raise RuntimeError("Set PDF_PATH or PDF_BASE64 to a real PDF")
    cert_pem = os.environ.get("CERT_PEM")
    key_pem = os.environ.get("KEY_PEM")
    if not cert_pem or not key_pem:
        raise RuntimeError("Set CERT_PEM and KEY_PEM to signing material")
    contract = AppointmentContract("apt-2026-1042", "p-1042", "completed", pdf, cert_pem, key_pem)
    print(json.dumps(sign_contract(contract, client, bucket), indent=2))


if __name__ == "__main__":
    main()
