"""Bounded local browser uploads, with byte identity and durable retry receipts."""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import shutil
import time
import uuid

from fastapi import HTTPException, Request

from oma.store import Conflict, canonical, digest

MAX_BYTES = 4 * 1024**3
RESERVE_BYTES = 30 * 1024**3


def register_upload(app, service):
    slots = asyncio.Semaphore(2)

    @app.post("/api/uploads", status_code=201)
    async def upload(request: Request, filename: str, idempotency_key: str | None = None):
        if (not filename or len(filename) > 180 or Path(filename).name != filename
                or any(ord(c) < 32 or c in '/\\:<>?*|"' for c in filename) or not filename.lower().endswith(".ifc")
                or filename.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
            raise HTTPException(422, "Provide a plain IFC file name without a directory")
        if idempotency_key is not None and not 1 <= len(idempotency_key) <= 256:
            raise HTTPException(422, "Upload retry key must contain 1 to 256 characters")
        length = request.headers.get("content-length")
        try:
            declared = int(length) if length is not None else None
        except ValueError:
            raise HTTPException(422, "Invalid upload length")
        if declared is not None and (declared < 1 or declared > MAX_BYTES):
            raise HTTPException(413, "Each IFC file must contain between 1 byte and 4 GiB")
        if request.headers.get("content-type", "").split(";")[0].lower() != "application/octet-stream":
            raise HTTPException(415, "Send the IFC file as application/octet-stream")
        store = service.store
        folder = store.directory / "uploads"
        folder.mkdir(exist_ok=True)
        if shutil.disk_usage(folder).free < RESERVE_BYTES + (declared or 1024**3):
            raise HTTPException(507, "The upload would exceed the local disk reserve")
        pending = folder / f".pending-{uuid.uuid4().hex}.ifc"
        h, size, header = hashlib.sha256(), 0, bytearray()
        began = time.monotonic()
        try:
            async with asyncio.timeout(600), slots:
                with pending.open("xb") as output:
                    async for block in request.stream():
                        if time.monotonic() - began > 600:
                            raise HTTPException(408, "Upload time budget exhausted")
                        size += len(block)
                        if size > MAX_BYTES or (declared is not None and size > declared):
                            raise HTTPException(413, "Actual uploaded bytes exceed the permitted length")
                        if len(header) < 4096:
                            header.extend(block[:4096-len(header)])
                        if len(header) >= 32 and not bytes(header).lstrip(b"\xef\xbb\xbf \r\n\t").startswith(b"ISO-10303-21;"):
                            raise HTTPException(422, "The uploaded bytes are not an IFC STEP file")
                        for start in range(0, len(block), 1024**2):
                            chunk = block[start:start+1024**2]
                            await asyncio.to_thread(output.write, chunk)
                            h.update(chunk)
                        if shutil.disk_usage(folder).free < RESERVE_BYTES:
                            raise HTTPException(507, "Upload stopped to preserve local disk reserve")
                    output.flush()
                    os.fsync(output.fileno())
                if not size or (declared is not None and size != declared):
                    raise HTTPException(422, "Upload was empty or incomplete")
                if not bytes(header).lstrip(b"\xef\xbb\xbf \r\n\t").startswith(b"ISO-10303-21;"):
                    raise HTTPException(422, "The uploaded bytes are not an IFC STEP file")
                source_hash = h.hexdigest()
                destination = folder / source_hash / filename
                response = {"path": str(destination), "sha256": source_hash, "size_bytes": size, "name": filename,
                            "status": "UPLOADED", "engineering_checks": "NOT_RUN"}
                request_hash = digest({"sha256": source_hash, "name": filename, "size_bytes": size})
                # Hashing a large existing file must never hold the database
                # publication lock or block durable controls for another job.
                if destination.exists():
                    from oma.ifc.audit import sha256_file
                    if await asyncio.to_thread(sha256_file, destination) != source_hash:
                        raise HTTPException(422, "Existing uploaded content has changed; import stopped")
                with store.transaction() as db:
                    if idempotency_key:
                        prior = db.execute("SELECT * FROM requests WHERE project_id='__uploads__' AND key=?", (idempotency_key,)).fetchone()
                        if prior:
                            if prior["request_hash"] != request_hash:
                                raise Conflict("Upload retry key was used with different file bytes or name")
                            # A retried upload supplies the same verified bytes.
                            # Repair a missing asset before replaying success.
                            destination.parent.mkdir(exist_ok=True)
                            if not destination.exists():
                                os.replace(pending, destination)
                            return response
                    destination.parent.mkdir(exist_ok=True)
                    if not destination.exists():
                        os.replace(pending, destination)
                    if idempotency_key:
                        db.execute("INSERT INTO requests VALUES('__uploads__',?,?,?)", (idempotency_key, request_hash, canonical(response).decode()))
                return response
        except TimeoutError:
            raise HTTPException(408, "Upload time budget exhausted")
        finally:
            if pending.exists():
                pending.unlink()
