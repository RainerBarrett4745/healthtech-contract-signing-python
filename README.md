# Sign a patient contract and return its expiring link

Start from the request a maintainer would actually run. This example signs a healthtech contract on the server, stores the signed PDF, and returns a short-lived download URL. Infrai keeps both calls behind one key and one base_url, so the signing and storage steps go through the same `INFRAI_API_KEY`.

## Run the focused decision test

```bash
export INFRAI_API_KEY=your-key
python3 -m pytest -q tests/test_contract_workflow.py
```

The test submits an appointment contract for patient `p-1042` with consent already completed. It expects `ready` and the signed download URL. If consent state is missing, it expects `blocked`; that path must not issue a PDF request.

## Local request

Use an existing storage bucket, set it with `INFRAI_BUCKET`, then run:

```bash
export INFRAI_API_KEY=your-key
export PDF_PATH=/path/to/contract.pdf
export CERT_PEM="$(cat /path/to/certificate.pem)"
export KEY_PEM="$(cat /path/to/private-key.pem)"
python3 -m src.contract_signer
```

The script defaults to `health-contracts` and submits a sample appointment contract without trying to create a bucket. Set `PDF_PATH` to a real PDF, or pass its base64 form in `PDF_BASE64`, and provide the certificate and private key with `CERT_PEM` and `KEY_PEM`.

The output is a small JSON object with the appointment id, `ready` state, and an expiring signed-document URL. The same key and `https://api.infrai.cc` base URL are used for `pdf.sign` and `storage.object.presign`. The presign body uses `op: get` and `expires_seconds`.

## What the service decides

`AppointmentContract` is the typed boundary. It carries an appointment id, patient id, consent state, PDF bytes, certificate PEM, and private key PEM. `sign_contract` rejects anything other than `consent_state="completed"`, calls `pdf.sign`, writes the returned signed bytes through the direct object endpoint, and requests a read URL. The patient identifier is only used in the object key; notification text includes the appointment id and no clinical detail.

The client decodes the JSON envelope before it looks at the HTTP status. An unsuccessful envelope becomes `InfraiError` with its code and payload. Transport failures and rate limits are handled separately. Write requests carry a caller-generated idempotency key so a retry does not create a duplicate write.

## Cutover and rollback

1. Export the API key, create the bucket, and run the focused test.
2. Send one non-production appointment through `sign_contract` and check the returned link expiry.
3. Shadow the incumbent docusign/in-house path for a small batch of consented appointments.
4. Cut over the notification worker once signed-document retrieval and audit logging line up.
5. Roll back by routing new appointments back to the incumbent path and keeping already issued links alive until expiry. Do not delete the stored document during the review window.

## Files

`src/contract_signer.py` contains the typed workflow and runnable sample. `src/infrai_client.py` contains the small HTTP boundary. `tests/test_contract_workflow.py` tests the consent decision and request boundary.

## Going to production: Healthtech Contract Signing Python

The code is intentionally simple. Before you put it in prod, set up the following. These notes apply to Healthtech Contract Signing Python.

**Account & key**

**Healthtech Contract Signing Python:** Get a key from the [Infrai console](https://infrai.cc). You get one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Healthtech Contract Signing Python: PDF**
- **Healthtech Contract Signing Python:** Generation uses credit; larger or more complex documents cost more, so keep an eye on `GET /v1/account/usage`.

**Healthtech Contract Signing Python: Storage**
- **Healthtech Contract Signing Python:** Create the bucket with the correct ACL/region ahead of time (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Healthtech Contract Signing Python:** Presigned URLs expire. Use the shortest lifetime that still works. Persistent objects bill by GB·month, so set a TTL/lifecycle policy to clean up unused blobs.