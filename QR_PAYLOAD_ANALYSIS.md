# QR Code Payload Analysis & Recommendations

## Current Implementation

### PayeeQRPayload (Step 1 - Payee Identity QR)

**Current Fields**:
```json
{
  "payeeId": "unique-user-id",
  "payeeName": "Ali Khan",
  "deviceId": "device-uuid",
  "nonce": "random-uuid"
}
```

**Purpose**: Identify the payee before generating a payment.

**Security Features**:
- ✅ `nonce`: Prevents QR code reuse
- ✅ `deviceId`: Verifies QR came from real device (not screenshot)
- ✅ `payeeId`: Unique user identifier

---

### TransactionPayloadQR (Step 2 - Transaction Payment QR)

**Current Fields**:
```json
{
  "txId": "tx-uuid",
  "payerId": "sender-user-id",
  "payeeId": "recipient-id",
  "amount": 50000,
  "timestamp": 1712345678901,
  "nonce": "random-uuid",
  "payerName": "Usman",
  "note": "optional note"
}
```

**Purpose**: Payment instruction from payer to payee.

**Security Features**:
- ✅ `txId`: Unique transaction ID
- ✅ `timestamp`: Used for freshness validation (±2 minutes)
- ✅ `nonce`: Prevents replay attacks
- ✅ `payerId` & `payeeId`: Ensures correct parties

---

## Recommended Additions for Production

### 1. **Cryptographic Signature** (HIGH PRIORITY)

**Field**: `signature` (Base64-encoded RSA-PSS signature)

**Why**:
- **Authenticity**: Proves transaction was created by the payer
- **Integrity**: Detects if transaction data was tampered with
- **Non-repudiation**: Payer cannot deny creating the transaction

**Implementation**:
```json
{
  "txId": "tx-uuid",
  "payerId": "sender-user-id",
  "payeeId": "recipient-id",
  "amount": 50000,
  "timestamp": 1712345678901,
  "nonce": "random-uuid",
  "payerName": "Usman",
  "note": "optional note",
  "signature": "base64-encoded-signature"  // NEW
}
```

**How It Works**:
1. Payer signs transaction payload with their private key
2. Payee verifies signature with payer's public key
3. If signature is invalid, transaction is rejected

**Backend Support**: ✅ Already implemented in `CryptoManager.sign_transaction()` and `verify_signature()`

**Android Support**: ⚠️ `TransactionSigner` exists but not integrated in new flow

---

### 2. **Timestamp in Payee QR** (MEDIUM PRIORITY)

**Field**: `timestamp` (currentTimeMillis)

**Why**:
- **Freshness**: Payer can validate QR is recent (not stale)
- **Replay Prevention**: Prevents using old payee QRs
- **Security**: Reduces window for QR code interception

**Implementation**:
```json
{
  "payeeId": "unique-user-id",
  "payeeName": "Ali Khan",
  "deviceId": "device-uuid",
  "nonce": "random-uuid",
  "timestamp": 1712345678901  // NEW
}
```

**Validation**:
- Payer checks timestamp is within ±5 minutes
- Rejects if QR is too old

---

### 3. **Public Key in Payee QR** (MEDIUM PRIORITY)

**Field**: `publicKey` (PEM format)

**Why**:
- **Signature Verification**: Enables payee to verify transaction signatures
- **Future-Proof**: Enables encrypted communication
- **Trust**: Payer can verify payee's identity cryptographically

**Implementation**:
```json
{
  "payeeId": "unique-user-id",
  "payeeName": "Ali Khan",
  "deviceId": "device-uuid",
  "nonce": "random-uuid",
  "publicKey": "-----BEGIN PUBLIC KEY-----\n..."  // NEW
}
```

**Note**: Public keys are safe to share (not secret)

---

### 4. **Currency Code** (LOW PRIORITY)

**Field**: `currency` (ISO 4217 code, e.g., "PKR")

**Why**:
- **Clarity**: Explicitly states currency (currently hardcoded to PKR)
- **Internationalization**: Supports multiple currencies
- **Validation**: Prevents currency mismatch errors

**Implementation**:
```json
{
  "txId": "tx-uuid",
  "payerId": "sender-user-id",
  "payeeId": "recipient-id",
  "amount": 50000,
  "currency": "PKR",  // NEW
  "timestamp": 1712345678901,
  "nonce": "random-uuid",
  "payerName": "Usman",
  "note": "optional note"
}
```

---

### 5. **Transaction Version** (LOW PRIORITY)

**Field**: `version` (integer, e.g., 1)

**Why**:
- **Compatibility**: Allows future protocol changes
- **Validation**: Payee can reject unsupported versions
- **Evolution**: Enables backward compatibility

**Implementation**:
```json
{
  "version": 1,  // NEW
  "txId": "tx-uuid",
  ...
}
```

---

## Security Analysis

### Current Security (MVP)

**Strengths**:
- ✅ Nonce prevents replay attacks
- ✅ Timestamp validation (±2 minutes)
- ✅ Payee ID matching prevents wrong recipient
- ✅ Device ID verification prevents screenshot attacks
- ✅ Biometric authentication required

**Weaknesses**:
- ❌ No cryptographic signature (transaction can be forged)
- ❌ No timestamp in Payee QR (stale QRs can be used)
- ❌ No public key (cannot verify signatures)

### With Recommended Additions

**Enhanced Security**:
- ✅ Cryptographic signature ensures authenticity
- ✅ Timestamp in Payee QR prevents stale QR usage
- ✅ Public key enables signature verification
- ✅ Currency code prevents currency confusion

---

## Implementation Priority

### Phase 1: MVP (Current)
- ✅ Basic fields (payeeId, payeeName, deviceId, nonce)
- ✅ Transaction fields (txId, payerId, payeeId, amount, timestamp, nonce)
- ✅ Local validation (amount, timestamp, payeeId matching)

### Phase 2: Enhanced Security (Recommended)
1. **Add Signature to TransactionPayloadQR** (HIGH)
   - Integrate `TransactionSigner.signTransaction()`
   - Add signature verification in `validateTransactionPayload()`
   - Update backend to verify signatures on sync

2. **Add Timestamp to PayeeQRPayload** (MEDIUM)
   - Add `timestamp` field
   - Validate freshness (±5 minutes)
   - Update `createPayeeQR()` and `parsePayeeQR()`

3. **Add Public Key to PayeeQRPayload** (MEDIUM)
   - Add `publicKey` field
   - Retrieve from wallet
   - Enable signature verification

### Phase 3: Production Hardening (Future)
- Add currency code
- Add version field
- Implement Android Keystore for private keys
- Add transaction counter for replay prevention
- Add hash verification for data integrity

---

## Code Changes Required

### For Signature Support

**1. Update TransactionPayloadQR**:
```kotlin
data class TransactionPayloadQR(
    val txId: String,
    val payerId: String,
    val payeeId: String,
    val amount: Long,
    val timestamp: Long,
    val nonce: String,
    val payerName: String,
    val note: String? = null,
    val signature: String? = null  // NEW
)
```

**2. Update QR Generation**:
```kotlin
// In SendPaymentScreen.kt
val transactionPayload = TransactionPayloadQR(...)
val signature = TransactionSigner.signTransaction(
    transactionData = mapOf(
        "txId" to transactionPayload.txId,
        "payerId" to transactionPayload.payerId,
        "payeeId" to transactionPayload.payeeId,
        "amount" to transactionPayload.amount,
        "timestamp" to transactionPayload.timestamp,
        "nonce" to transactionPayload.nonce
    ),
    privateKeyPem = privateKey
)
val signedPayload = transactionPayload.copy(signature = signature)
```

**3. Update Validation**:
```kotlin
// In QRCodeHelper.kt
fun validateTransactionPayload(
    payload: TransactionPayloadQR,
    currentPayeeId: String,
    payerPublicKey: String? = null  // NEW
): ValidationResult {
    // Existing validations...
    
    // NEW: Verify signature if public key provided
    if (payerPublicKey != null && payload.signature != null) {
        val isValid = TransactionSigner.verifySignature(
            transactionData = mapOf(...),
            signatureB64 = payload.signature,
            publicKeyPEM = payerPublicKey
        )
        if (!isValid) {
            return ValidationResult(false, "Invalid transaction signature")
        }
    }
    
    return ValidationResult(true, "Valid transaction payload")
}
```

---

## Summary

### Current MVP Fields: ✅ Sufficient for Basic Functionality

**PayeeQRPayload**: `{ payeeId, payeeName, deviceId, nonce }`
**TransactionPayloadQR**: `{ txId, payerId, payeeId, amount, timestamp, nonce, payerName, note }`

### Recommended Production Fields:

**PayeeQRPayload** (add):
- `timestamp` (for freshness validation)
- `publicKey` (for signature verification)

**TransactionPayloadQR** (add):
- `signature` (for authenticity and integrity) ⭐ **HIGHEST PRIORITY**
- `currency` (for clarity and internationalization)

### Security Impact:

- **Current**: Basic security (nonce, timestamp, ID matching)
- **With Signature**: Strong security (cryptographic proof of authenticity)
- **With All Recommendations**: Production-grade security

---

**Recommendation**: For MVP, current fields are sufficient. For production deployment, **add signature support** as the highest priority enhancement.

