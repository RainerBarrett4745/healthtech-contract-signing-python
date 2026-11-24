from src.contract_signer import AppointmentContract, sign_contract


class FakeClient:
    def __init__(self):
        self.calls = []

    def sign(self, pdf, cert_pem, key_pem):
        self.calls.append(("sign", pdf, cert_pem, key_pem))
        return b"signed-pdf"

    def put_object(self, bucket, key, content):
        self.calls.append(("put", bucket, key, content))

    def signed_download(self, bucket, key):
        self.calls.append(("get", bucket, key))
        return "https://download.test/contract"


def test_completed_consent_publishes_a_patient_safe_link():
    client = FakeClient()
    contract = AppointmentContract("apt-7", "p-7", "completed", b"pdf", "cert", "key")

    result = sign_contract(contract, client)

    assert result == {"appointment_id": "apt-7", "state": "ready", "download_url": "https://download.test/contract"}
    assert [call[0] for call in client.calls] == ["sign", "put", "get"]
    assert "p-7" in client.calls[1][2]


def test_incomplete_consent_blocks_signing_and_storage():
    client = FakeClient()
    contract = AppointmentContract("apt-8", "p-8", "pending", b"pdf", "cert", "key")

    assert sign_contract(contract, client) == {"appointment_id": "apt-8", "state": "blocked"}
    assert client.calls == []

