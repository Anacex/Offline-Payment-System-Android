"""Unit tests for sync endpoints."""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from decimal import Decimal
import json
from app.core.crypto import CryptoManager
from app.api.v1.offline_transaction import GENESIS_PREV_HASH, _ledger_entry_hash_hex
from app.models.wallet import DeviceLedgerHead, OfflineReceiverSync

from tests.auth_helpers import get_auth_headers


def create_test_transaction_data(sender_wallet_id, receiver_public_key, amount, nonce=None):
    """Helper to create valid transaction data for testing."""
    if nonce is None:
        nonce = CryptoManager.generate_nonce()
    
    transaction_data = {
        "sender_wallet_id": sender_wallet_id,
        "receiver_public_key": receiver_public_key,
        "amount": str(amount),
        "currency": "PKR",
        "nonce": nonce,
        "timestamp": datetime.utcnow().isoformat()
    }
    return transaction_data


def create_receiver_sync_request(
    receiver_wallet,
    *,
    amount="25.00",
    payer_id="payer_1",
    payee_id="99",
    nonce=None,
    tx_id=None,
    device_fingerprint="receiver_sync_device",
):
    """Build a RECEIVED-direction sync row signed by the receiver's offline wallet (matches Android + API)."""
    if nonce is None:
        nonce = CryptoManager.generate_nonce()
    if tx_id is None:
        tx_id = CryptoManager.generate_nonce()
    ts = datetime.utcnow().isoformat()
    transaction_data = {
        "direction": "RECEIVED",
        "receiver_wallet_id": receiver_wallet.id,
        "amount": str(amount),
        "currency": "PKR",
        "nonce": nonce,
        "timestamp": ts,
        "payer_id": payer_id,
        "payee_id": payee_id,
        "tx_id": tx_id,
    }
    signature = CryptoManager.sign_transaction(
        transaction_data, receiver_wallet.private_key_encrypted
    )
    return {
        "transaction_data": transaction_data,
        "signature": signature,
        "receipt": {"receipt_hash": "recv_rh_test"},
        "device_fingerprint": device_fingerprint,
        "txId": tx_id,
    }


def create_sync_transaction_request(transaction_data, signature, receipt=None):
    """Helper to create sync transaction request."""
    if receipt is None:
        receipt = CryptoManager.create_transaction_receipt(
            sender_wallet_id=transaction_data["sender_wallet_id"],
            receiver_public_key=transaction_data["receiver_public_key"],
            amount=float(transaction_data["amount"]),
            currency=transaction_data["currency"],
            nonce=transaction_data["nonce"],
            signature=signature,
            timestamp=transaction_data["timestamp"]
        )
    
    return {
        "transaction_data": transaction_data,
        "signature": signature,
        "receipt": receipt,
        "device_fingerprint": "test_device_123"
    }


@pytest.mark.unit
def test_sync_endpoint_requires_auth(client: TestClient):
    """Test that sync endpoint requires authentication."""
    payload = {"transactions": []}
    response = client.post("/api/v1/offline-transactions/sync", json=payload)
    assert response.status_code == 401


@pytest.mark.unit
def test_sync_empty_transactions(client: TestClient, test_user):
    """Test syncing with empty transaction list."""
    headers = get_auth_headers(client, test_user, unique_device=True)
    
    payload = {"transactions": []}
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 0
    assert len(body["results"]) == 0
    assert "message" in body


@pytest.mark.unit
def test_sync_missing_required_fields(client: TestClient, test_user_with_wallets):
    """Test sync fails when required fields are missing."""
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Missing receiver_public_key
    transaction_data = {
        "sender_wallet_id": offline_wallet.id,
        "amount": "50.00",
        "currency": "PKR",
        "nonce": CryptoManager.generate_nonce()
    }
    
    payload = {
        "transactions": [{
            "transaction_data": transaction_data,
            "signature": "fake_signature"
        }]
    }
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert len(body["results"]) == 1
    assert body["results"][0]["result"] == "failed"
    assert "Missing required fields" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_missing_signature(client: TestClient, test_user_with_wallets):
    """Test sync fails when signature is missing."""
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        50.00
    )
    
    payload = {
        "transactions": [{
            "transaction_data": transaction_data
            # Missing signature
        }]
    }
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert body["results"][0]["result"] == "failed"
    assert "Invalid or missing transaction signature" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_invalid_sender_wallet(client: TestClient, test_user_with_wallets):
    """Test sync fails when sender wallet doesn't exist or doesn't belong to user."""
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    
    transaction_data = create_test_transaction_data(
        99999,  # Non-existent wallet ID
        "receiver_public_key_123",
        50.00
    )
    
    signature = "fake_signature"
    sync_req = create_sync_transaction_request(transaction_data, signature)
    
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert body["results"][0]["result"] == "failed"
    assert "Sender wallet not found" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_invalid_amount_zero(client: TestClient, test_user_with_wallets):
    """Test sync fails when amount is zero or negative."""
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Test with zero amount
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        0.00
    )
    
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert body["results"][0]["result"] == "failed"
    assert "Amount must be greater than 0" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_duplicate_nonce(client: TestClient, test_user_with_wallets, db_session):
    """Test sync fails when nonce already exists (replay attack prevention)."""
    from app.models.wallet import OfflineTransaction
    
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Create a transaction with a specific nonce
    nonce = CryptoManager.generate_nonce()
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        50.00,
        nonce=nonce
    )
    
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    
    # First, create an existing transaction with this nonce
    existing_tx = OfflineTransaction(
        sender_wallet_id=offline_wallet.id,
        receiver_public_key="receiver_public_key_123",
        amount=Decimal("50.00"),
        currency="PKR",
        transaction_signature=signature,
        nonce=nonce,
        receipt_hash="hash123",
        receipt_data="{}",
        status="synced",
        created_at_device=datetime.utcnow()
    )
    db_session.add(existing_tx)
    db_session.commit()
    
    # Try to sync the same transaction again
    sync_req = create_sync_transaction_request(transaction_data, signature)
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert body["results"][0]["result"] == "failed"
    assert "Duplicate transaction" in body["results"][0]["error_reason"] or "nonce already exists" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_success_single_transaction(client: TestClient, test_user_with_wallets, db_session):
    """Test successful sync of a single transaction with balance updates."""
    from app.models.wallet import Wallet
    
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Create receiver wallet
    receiver_public_key, receiver_private_key = CryptoManager.generate_key_pair()
    receiver_wallet = Wallet(
        user_id=test_user_with_wallets["user"].id,
        wallet_type="offline",
        currency="PKR",
        balance=100.00,
        public_key=receiver_public_key,
        private_key_encrypted=receiver_private_key,
        bank_account_number="receiver_account_123",
        is_active=True,
    )
    db_session.add(receiver_wallet)
    db_session.commit()
    db_session.refresh(receiver_wallet)
    
    # Get initial balances
    db_session.refresh(offline_wallet)
    initial_sender_balance = Decimal(str(offline_wallet.balance))
    initial_receiver_balance = Decimal(str(receiver_wallet.balance))
    transfer_amount = Decimal("50.00")
    
    # Create transaction
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        float(transfer_amount)
    )
    
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 1
    assert body["total_failed"] == 0
    assert len(body["results"]) == 1
    assert body["results"][0]["result"] == "synced"
    assert body["results"][0]["transaction_id"] is not None
    assert body["results"][0]["error_reason"] is None
    
    # Verify balances were updated
    db_session.refresh(offline_wallet)
    db_session.refresh(receiver_wallet)
    
    expected_sender_balance = initial_sender_balance - transfer_amount
    expected_receiver_balance = initial_receiver_balance + transfer_amount
    
    assert Decimal(str(offline_wallet.balance)) == expected_sender_balance
    assert Decimal(str(receiver_wallet.balance)) == expected_receiver_balance


@pytest.mark.unit
def test_sync_multiple_transactions_mixed_results(client: TestClient, test_user_with_wallets, db_session):
    """Test syncing multiple transactions where some succeed and some fail."""
    from app.models.wallet import Wallet
    
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Create receiver wallet
    receiver_public_key, receiver_private_key = CryptoManager.generate_key_pair()
    receiver_wallet = Wallet(
        user_id=test_user_with_wallets["user"].id,
        wallet_type="offline",
        currency="PKR",
        balance=100.00,
        public_key=receiver_public_key,
        private_key_encrypted=receiver_private_key,
        bank_account_number="receiver_account_123",
        is_active=True,
    )
    db_session.add(receiver_wallet)
    db_session.commit()
    db_session.refresh(receiver_wallet)
    
    transactions = []
    
    # Valid transaction 1
    tx1_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        25.00
    )
    tx1_signature = CryptoManager.sign_transaction(tx1_data, offline_wallet.private_key_encrypted)
    transactions.append(create_sync_transaction_request(tx1_data, tx1_signature))
    
    # Invalid transaction - missing amount
    tx2_data = {
        "sender_wallet_id": offline_wallet.id,
        "receiver_public_key": receiver_public_key,
        "currency": "PKR",
        "nonce": CryptoManager.generate_nonce(),
        "timestamp": datetime.utcnow().isoformat()
    }
    transactions.append({
        "transaction_data": tx2_data,
        "signature": "fake_signature"
    })
    
    # Valid transaction 2
    tx3_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        30.00
    )
    tx3_signature = CryptoManager.sign_transaction(tx3_data, offline_wallet.private_key_encrypted)
    transactions.append(create_sync_transaction_request(tx3_data, tx3_signature))
    
    # Invalid transaction - zero amount
    tx4_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        0.00
    )
    tx4_signature = CryptoManager.sign_transaction(tx4_data, offline_wallet.private_key_encrypted)
    transactions.append(create_sync_transaction_request(tx4_data, tx4_signature))
    
    payload = {"transactions": transactions}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 2
    assert body["total_failed"] == 2
    assert len(body["results"]) == 4
    
    # Check results
    synced_results = [r for r in body["results"] if r["result"] == "synced"]
    failed_results = [r for r in body["results"] if r["result"] == "failed"]
    
    assert len(synced_results) == 2
    assert len(failed_results) == 2
    
    # Verify all synced transactions have transaction_id
    for result in synced_results:
        assert result["transaction_id"] is not None
        assert result["error_reason"] is None
    
    # Verify all failed transactions have error_reason
    for result in failed_results:
        assert result["error_reason"] is not None


@pytest.mark.unit
def test_sync_receiver_wallet_not_found(client: TestClient, test_user_with_wallets):
    """Test sync succeeds even if receiver wallet doesn't exist (will be created later)."""
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    # Use a public key that doesn't match any wallet
    receiver_public_key, _ = CryptoManager.generate_key_pair()
    
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        50.00
    )
    
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    # Transaction should still sync successfully even if receiver wallet not found
    # (receiver balance won't be updated, but transaction is recorded)
    assert body["total_synced"] == 1
    assert body["results"][0]["result"] == "synced"


@pytest.mark.unit
def test_sync_invalid_amount_format(client: TestClient, test_user_with_wallets):
    """Test sync fails with invalid amount format."""
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        50.00
    )
    transaction_data["amount"] = "not_a_number"  # Invalid format

    # Real signature over this payload so verification passes and amount parsing runs
    signature = CryptoManager.sign_transaction(
        transaction_data, offline_wallet.private_key_encrypted
    )
    sync_req = {
        "transaction_data": transaction_data,
        "signature": signature,
        "receipt": {},
        "device_fingerprint": "test_device_123",
    }

    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert body["results"][0]["result"] == "failed"
    assert "Invalid amount format" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_response_structure(client: TestClient, test_user_with_wallets, db_session):
    """Test that sync response has correct structure."""
    from app.models.wallet import Wallet
    
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]
    
    receiver_public_key, receiver_private_key = CryptoManager.generate_key_pair()
    receiver_wallet = Wallet(
        user_id=test_user_with_wallets["user"].id,
        wallet_type="offline",
        currency="PKR",
        balance=100.00,
        public_key=receiver_public_key,
        private_key_encrypted=receiver_private_key,
        is_active=True,
    )
    db_session.add(receiver_wallet)
    db_session.commit()
    
    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        receiver_public_key,
        50.00
    )
    
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    
    payload = {"transactions": [sync_req]}
    
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    
    # Verify response structure
    assert "message" in body
    assert "results" in body
    assert "total_synced" in body
    assert "total_failed" in body
    
    # Verify result structure
    if len(body["results"]) > 0:
        result = body["results"][0]
        assert "transaction_id" in result or result.get("transaction_id") is None
        assert "reference" in result
        assert "result" in result
        assert result["result"] in ["synced", "failed"]
        if result["result"] == "failed":
            assert "error_reason" in result


@pytest.mark.unit
def test_sync_ledger_incomplete_fields(client: TestClient, test_user_with_wallets):
    """Partial ledger fields must be rejected."""
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]

    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        50.00,
    )
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    sync_req["ledger_entry_hash"] = "a" * 64

    payload = {"transactions": [sync_req]}
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    assert body["results"][0]["error_reason"] == "LEDGER_INTEGRITY_INCOMPLETE_FIELDS"


@pytest.mark.unit
def test_sync_ledger_failure_flags_user_blocked(client: TestClient, test_user_with_wallets, db_session):
    """Ledger integrity failure on sync suspends the sender account for review."""
    from app.models.user import User

    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]

    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        50.00,
    )
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    canon = '{"ledger":"tampered"}'
    sync_req["ledger_prev_hash"] = GENESIS_PREV_HASH
    sync_req["ledger_sequence"] = 1
    sync_req["integrity_canonical_json"] = canon
    sync_req["ledger_entry_hash"] = "f" * 64

    payload = {"transactions": [sync_req]}
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_failed"] == 1

    uid = test_user_with_wallets["user"].id
    db_session.expire_all()
    user = db_session.query(User).filter(User.id == uid).first()
    assert user.account_blocked is True
    assert user.fraud_review_pending is True
    assert user.account_blocked_reason is not None


@pytest.mark.unit
def test_sync_ledger_hash_mismatch(client: TestClient, test_user_with_wallets):
    """Wrong entry hash vs canonical JSON is flagged."""
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]

    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        50.00,
    )
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    canon = '{"ledger":"test"}'
    sync_req["ledger_prev_hash"] = GENESIS_PREV_HASH
    sync_req["ledger_sequence"] = 1
    sync_req["integrity_canonical_json"] = canon
    sync_req["ledger_entry_hash"] = "f" * 64

    payload = {"transactions": [sync_req]}
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 0
    assert body["total_failed"] == 1
    # When the server has never seen this device_fingerprint, mismatches are treated as non-blocking.
    assert body["results"][0]["error_reason"] in (
        "LEDGER_INTEGRITY_HASH_MISMATCH_FIRST_SEEN_DEVICE",
        "LEDGER_INTEGRITY_HASH_MISMATCH",
    )


@pytest.mark.unit
def test_sync_ledger_hash_mismatch_first_seen_device_does_not_block(
    client: TestClient, test_user_with_wallets, db_session
):
    """A first-seen device hash mismatch should fail the row but NOT suspend the account."""
    from app.models.user import User

    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]

    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        50.00,
    )
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    canon = '{"ledger":"first_seen_bad"}'
    sync_req["device_fingerprint"] = "new_device_after_reinstall"
    sync_req["ledger_prev_hash"] = GENESIS_PREV_HASH
    sync_req["ledger_sequence"] = 1
    sync_req["integrity_canonical_json"] = canon
    sync_req["ledger_entry_hash"] = "f" * 64

    response = client.post("/api/v1/offline-transactions/sync", json={"transactions": [sync_req]}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_failed"] == 1
    assert body["results"][0]["error_reason"] == "LEDGER_INTEGRITY_HASH_MISMATCH_FIRST_SEEN_DEVICE"

    uid = test_user_with_wallets["user"].id
    db_session.expire_all()
    user = db_session.query(User).filter(User.id == uid).first()
    assert user.account_blocked is False
    assert user.fraud_review_pending is False


@pytest.mark.unit
def test_sync_ledger_success_updates_head(client: TestClient, test_user_with_wallets, db_session):
    """Valid chain fields sync and persist DeviceLedgerHead for the device."""
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    offline_wallet = test_user_with_wallets["offline_wallet"]

    transaction_data = create_test_transaction_data(
        offline_wallet.id,
        "receiver_public_key_123",
        50.00,
    )
    signature = CryptoManager.sign_transaction(transaction_data, offline_wallet.private_key_encrypted)
    sync_req = create_sync_transaction_request(transaction_data, signature)
    canon = '{"ledger":"ok"}'
    entry = _ledger_entry_hash_hex(GENESIS_PREV_HASH, canon)
    sync_req["ledger_prev_hash"] = GENESIS_PREV_HASH
    sync_req["ledger_sequence"] = 1
    sync_req["integrity_canonical_json"] = canon
    sync_req["ledger_entry_hash"] = entry

    payload = {"transactions": [sync_req]}
    response = client.post("/api/v1/offline-transactions/sync", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 1
    assert body["total_failed"] == 0

    uid = test_user_with_wallets["user"].id
    head = (
        db_session.query(DeviceLedgerHead)
        .filter(
            DeviceLedgerHead.user_id == uid,
            DeviceLedgerHead.device_fingerprint == "test_device_123",
        )
        .first()
    )
    assert head is not None
    assert head.last_sequence == 1
    assert head.last_entry_hash.lower() == entry.lower()


@pytest.mark.unit
def test_sync_receiver_success_audit_only_no_server_balance_change(
    client: TestClient, test_user_with_wallets, db_session
):
    """Receiver RECEIVED sync is audit-only: wallet balances on server are unchanged."""
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    recv = test_user_with_wallets["offline_wallet"]
    db_session.refresh(recv)
    bal_before = Decimal(str(recv.balance))

    sync_req = create_receiver_sync_request(recv)
    response = client.post(
        "/api/v1/offline-transactions/sync",
        json={"transactions": [sync_req]},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 1
    assert body["total_failed"] == 0
    assert body["results"][0]["result"] == "synced"

    db_session.refresh(recv)
    assert Decimal(str(recv.balance)) == bal_before

    row = (
        db_session.query(OfflineReceiverSync)
        .filter(OfflineReceiverSync.payment_nonce == sync_req["transaction_data"]["nonce"])
        .first()
    )
    assert row is not None
    assert row.receiver_wallet_id == recv.id


@pytest.mark.unit
def test_sync_receiver_duplicate_nonce_idempotent(
    client: TestClient, test_user_with_wallets, db_session
):
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    recv = test_user_with_wallets["offline_wallet"]
    sync_req = create_receiver_sync_request(recv)
    payload = {"transactions": [sync_req, sync_req]}
    response = client.post(
        "/api/v1/offline-transactions/sync", json=payload, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 2
    assert body["total_failed"] == 0
    for r in body["results"]:
        assert r["result"] == "synced"


@pytest.mark.unit
def test_sync_receiver_signature_verification_fails(
    client: TestClient, test_user_with_wallets
):
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    recv = test_user_with_wallets["offline_wallet"]
    sync_req = create_receiver_sync_request(recv)
    sync_req["transaction_data"] = {
        **sync_req["transaction_data"],
        "amount": "999.00",
    }
    response = client.post(
        "/api/v1/offline-transactions/sync",
        json={"transactions": [sync_req]},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_failed"] == 1
    assert "Signature verification failed" in body["results"][0]["error_reason"]


@pytest.mark.unit
def test_sync_receiver_ledger_success_updates_head(
    client: TestClient, test_user_with_wallets, db_session
):
    fp = "receiver_ledger_fp"
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    recv = test_user_with_wallets["offline_wallet"]
    sync_req = create_receiver_sync_request(recv, device_fingerprint=fp)
    canon = '{"receiver_ledger":"ok"}'
    entry = _ledger_entry_hash_hex(GENESIS_PREV_HASH, canon)
    sync_req["ledger_prev_hash"] = GENESIS_PREV_HASH
    sync_req["ledger_sequence"] = 1
    sync_req["integrity_canonical_json"] = canon
    sync_req["ledger_entry_hash"] = entry

    response = client.post(
        "/api/v1/offline-transactions/sync",
        json={"transactions": [sync_req]},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_synced"] == 1

    uid = test_user_with_wallets["user"].id
    head = (
        db_session.query(DeviceLedgerHead)
        .filter(
            DeviceLedgerHead.user_id == uid,
            DeviceLedgerHead.device_fingerprint == fp,
        )
        .first()
    )
    assert head is not None
    assert head.last_sequence == 1
    assert head.last_entry_hash.lower() == entry.lower()


@pytest.mark.unit
def test_sync_receiver_ledger_failure_flags_user_blocked(
    client: TestClient, test_user_with_wallets, db_session
):
    from app.models.user import User

    fp = "receiver_ledger_bad"
    headers = get_auth_headers(client, test_user_with_wallets, unique_device=True)
    recv = test_user_with_wallets["offline_wallet"]
    sync_req = create_receiver_sync_request(recv, device_fingerprint=fp)
    canon = '{"receiver_ledger":"tampered"}'
    sync_req["ledger_prev_hash"] = GENESIS_PREV_HASH
    sync_req["ledger_sequence"] = 1
    sync_req["integrity_canonical_json"] = canon
    sync_req["ledger_entry_hash"] = "f" * 64

    response = client.post(
        "/api/v1/offline-transactions/sync",
        json={"transactions": [sync_req]},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_failed"] == 1

    uid = test_user_with_wallets["user"].id
    db_session.expire_all()
    user = db_session.query(User).filter(User.id == uid).first()
    assert user.account_blocked is True
    assert user.fraud_review_pending is True
