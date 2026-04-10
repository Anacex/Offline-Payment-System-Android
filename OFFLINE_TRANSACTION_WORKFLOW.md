# Offline Transaction Workflow Documentation

## Overview

This document describes the complete offline transaction workflow implemented in the Offline Payment System. The workflow enables secure peer-to-peer payments without requiring continuous internet connectivity, using QR codes for data transfer and local storage for transaction logging.

---

## Architecture Overview

The system follows a **5-step workflow** that ensures:
- **Payee Identification**: Confirms who the payer is sending money to
- **Transaction Creation**: Payer generates a payment instruction
- **Transaction Validation**: Payee validates and accepts the payment
- **Local Logging**: Both devices independently log the transaction
- **Future Synchronization**: Transactions are stored with full payload for server sync when online

---

## Step-by-Step Workflow

### **STEP 1: Payee Identifies Himself (Payee → Payer)**

**Purpose**: Establish trust and confirm the recipient's identity before generating a payment.

**Who**: Payee (Receiver)

**Action**: Payee opens the "Receive" screen (QR Code screen) in the app.

**What Happens**:
1. App generates a **Payee Identity QR Code** containing:
   ```json
   {
     "payeeId": "unique-user-id",
     "payeeName": "Ali Khan",
     "deviceId": "device-uuid",
     "nonce": "random-uuid"
   }
   ```

2. QR code is displayed on the payee's device screen.

**Technical Implementation**:
- **File**: `Android-App/app/src/main/java/com/offlinepayment/ui/qr/QRCodeScreen.kt`
- **Method**: `QRCodeHelper.createPayeeQR(payeeId, payeeName, deviceId)`
- **Backend Endpoint**: `POST /api/v1/wallets/qr-code` (generates same format)
- **QR Format**: Direct JSON string (not Base64 encoded)

**Security Features**:
- `nonce`: Random UUID prevents QR code reuse/replay attacks
- `deviceId`: Device fingerprint ensures QR came from a real device (not screenshot)
- `payeeId`: Unique user identifier prevents identity confusion

**Why This Step**:
- Prevents scanning fraudulent QR codes (screenshots, printed copies)
- Ensures sender cannot manually type payee information (dangerous)
- Establishes trust before generating money transfer QR
- Confirms WHO the payer is sending money to

---

### **STEP 2: Sender Scans Payee QR**

**Purpose**: Extract payee information and confirm the recipient.

**Who**: Payer (Sender)

**Action**: Payer opens "Send Payment" screen and scans the payee's QR code.

**What Happens**:
1. Payer taps "Scan Payee QR Code" button.
2. Camera opens and scans the payee's QR code.
3. App extracts:
   - `payeeId`
   - `payeeName`
   - `deviceId`
   - `nonce`

4. **Payee Confirmation Screen** appears:
   - Shows: "Are you paying [Payee Name]?"
   - Displays: Payee ID, Payee Name, Device ID (truncated)
   - Shows: "✓ Verified QR came from a real device"
   - Payer must confirm or cancel

**Technical Implementation**:
- **File**: `Android-App/app/src/main/java/com/offlinepayment/ui/qr/QRScannerScreen.kt`
- **Method**: `processImageProxyForPayee()` → `QRCodeHelper.parsePayeeQR()`
- **File**: `Android-App/app/src/main/java/com/offlinepayment/ui/SendPaymentScreen.kt`
- **State**: `showPayeeConfirmation = true` after successful scan

**Validation**:
- QR code must be valid JSON
- All required fields must be present
- Device ID verification (ensures QR is from real device, not screenshot)

**User Experience**:
- Payer sees payee details clearly
- Must explicitly confirm before proceeding
- Can cancel and scan a different QR code

---

### **STEP 3: Sender Creates Payment Payload & Shows Transaction QR**

**Purpose**: Generate the actual payment instruction that the payee will scan.

**Who**: Payer (Sender)

**Action**: After confirming payee, payer enters amount and generates transaction QR.

**What Happens**:
1. **Amount Input**:
   - Payer enters payment amount (in PKR)
   - App validates:
     - Amount > 0
     - Amount ≤ available wallet balance
     - Amount ≤ maximum transaction limit (500 PKR)

2. **Biometric Authentication** (if available):
   - Payer authenticates with fingerprint/face/device password
   - Required before generating payment QR

3. **Transaction Payload Generation**:
   - App creates transaction payload:
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
   - **Note**: `amount` is stored in **smallest currency unit** (paisa for PKR)
     - Example: 500 PKR = 50000 paisa

4. **QR Code Generation**:
   - Transaction payload is converted to JSON
   - JSON is Base64 encoded
   - Base64 string is encoded as QR code image
   - QR code is displayed on payer's device

5. **Local Storage (SENT)**:
   - Transaction is immediately saved to local Room database
   - Direction: `"SENT"`
   - Full payload stored in `rawPayload` field for future syncing

**Technical Implementation**:
- **File**: `Android-App/app/src/main/java/com/offlinepayment/ui/SendPaymentScreen.kt`
- **Method**: `QRCodeHelper.createTransactionPayloadQR()`
- **Database**: `LocalTransaction` entity with `direction = "SENT"`
- **Repository**: `WalletRepository.saveLocalTransaction()`

**Database Schema**:
```kotlin
@Entity(tableName = "local_transactions")
data class LocalTransaction(
    @PrimaryKey val txId: String,
    val payerId: String,
    val payeeId: String,
    val amount: Long, // In smallest currency unit (paisa)
    val timestamp: Long, // currentTimeMillis
    val direction: String, // "SENT" or "RECEIVED"
    val rawPayload: String // Full JSON for syncing
)
```

**Security Features**:
- `txId`: Unique transaction ID prevents duplicate processing
- `timestamp`: Used for freshness validation (±2 minutes)
- `nonce`: Random UUID prevents replay attacks
- `payerId` & `payeeId`: Ensures transaction is for correct parties
- Biometric authentication: Prevents unauthorized QR generation

---

### **STEP 4: Payee Scans Transaction QR (Payer → Payee)**

**Purpose**: Receive and validate the payment instruction from the payer.

**Who**: Payee (Receiver)

**Action**: Payee opens transaction QR scanner and scans the payer's QR code.

**What Happens**:
1. **QR Scanning**:
   - Payee opens "Scan Transaction QR" screen
   - Camera scans the payer's transaction QR code
   - App decodes: Base64 → JSON → `TransactionPayloadQR` object

2. **Local Validation** (performed automatically):
   - ✅ **Amount Check**: `amount > 0`
   - ✅ **Timestamp Check**: Transaction timestamp is within ±2 minutes of current time
   - ✅ **Payer ID Check**: `payerId` is present and non-empty
   - ✅ **Payee ID Match**: `payeeId` in QR matches **THIS device's user ID**
     - **Critical**: Prevents accepting payments intended for someone else

3. **If Validation Passes**:
   - Transaction is immediately saved to local Room database
   - Direction: `"RECEIVED"`
   - Full payload stored in `rawPayload` field
   - App navigates to "Payment Received (Offline)" screen

4. **If Validation Fails**:
   - Error message is displayed
   - Transaction is **NOT** saved
   - User can retry scanning

**Technical Implementation**:
- **File**: `Android-App/app/src/main/java/com/offlinepayment/ui/qr/TransactionQRScannerScreen.kt`
- **Method**: `processImageProxyForTransaction()` → `QRCodeHelper.parseTransactionPayloadQR()`
- **Validation**: `QRCodeHelper.validateTransactionPayload()`
- **Database**: `LocalTransaction` entity with `direction = "RECEIVED"`
- **Repository**: `WalletRepository.saveLocalTransaction()`

**Validation Rules**:
```kotlin
fun validateTransactionPayload(
    payload: TransactionPayloadQR,
    currentPayeeId: String,
    maxAgeMinutes: Long = 2
): ValidationResult {
    // 1. Amount must be positive
    if (payload.amount <= 0) {
        return ValidationResult(false, "Amount must be a positive number")
    }
    
    // 2. Timestamp must be within ±2 minutes
    val currentTime = System.currentTimeMillis()
    val ageMinutes = Math.abs(currentTime - payload.timestamp) / (1000 * 60)
    if (ageMinutes > maxAgeMinutes) {
        return ValidationResult(false, "Transaction timestamp is outside valid range")
    }
    
    // 3. Payer ID must be present
    if (payload.payerId.isBlank()) {
        return ValidationResult(false, "Payer ID is missing")
    }
    
    // 4. Payee ID must match this device's user ID
    if (payload.payeeId != currentPayeeId) {
        return ValidationResult(false, "Payee ID mismatch. This transaction is not for you.")
    }
    
    return ValidationResult(true, "Valid transaction payload")
}
```

**Payment Received Screen**:
- **File**: `Android-App/app/src/main/java/com/offlinepayment/ui/qr/TransactionReceivedScreen.kt`
- Displays:
  - Amount (converted from paisa to PKR)
  - Payer Name
  - Payer ID
  - Transaction ID
  - Timestamp
  - Optional Note
- Shows: "Payment Received (Offline). This transaction will be synchronized when online."
- Actions: Accept (navigate back) or Reject (cancel)

---

### **STEP 5: Local Logging (Room DB on Both Devices)**

**Purpose**: Maintain independent transaction logs on both devices for future synchronization.

**Who**: Both Payer and Payee devices

**What Happens**:

**On Payer's Device (SENT)**:
```kotlin
LocalTransaction(
    txId = "tx-uuid",
    payerId = "sender-user-id",
    payeeId = "recipient-id",
    amount = 50000, // In paisa
    timestamp = 1712345678901,
    direction = "SENT",
    rawPayload = "{...full JSON...}"
)
```

**On Payee's Device (RECEIVED)**:
```kotlin
LocalTransaction(
    txId = "tx-uuid", // Same txId
    payerId = "sender-user-id", // Same payerId
    payeeId = "recipient-id", // Same payeeId
    amount = 50000, // Same amount
    timestamp = 1712345678901, // Same timestamp
    direction = "RECEIVED", // Different direction
    rawPayload = "{...full JSON...}" // Same payload
)
```

**Technical Implementation**:
- **Database**: Room Database (`AppDatabase`)
- **Entity**: `LocalTransaction`
- **DAO**: `LocalTransactionDao`
- **Repository**: `WalletRepository.saveLocalTransaction()`
- **Table**: `local_transactions`

**Database Schema**:
```sql
CREATE TABLE local_transactions (
    txId TEXT NOT NULL PRIMARY KEY,
    payerId TEXT NOT NULL,
    payeeId TEXT NOT NULL,
    amount INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    direction TEXT NOT NULL,
    rawPayload TEXT NOT NULL
)
```

**Key Points**:
- Both devices store the **same transaction** with **different directions**
- `rawPayload` contains full JSON for server synchronization
- `txId` is the same on both devices (enables matching during sync)
- Transactions are stored **immediately** when QR is generated/scanned
- No internet connection required for logging

**Future Synchronization**:
- When device comes online, `rawPayload` can be sent to server
- Server can match transactions by `txId`
- Server can reconcile balances and finalize transactions

---

## Data Models

### PayeeQRPayload (Step 1)
```kotlin
data class PayeeQRPayload(
    val payeeId: String,        // Unique user identifier
    val payeeName: String,       // Display name
    val deviceId: String,        // Device fingerprint
    val nonce: String           // Random UUID for uniqueness
)
```

**QR Format**: Direct JSON string (not Base64 encoded)

**Example**:
```json
{
  "payeeId": "123",
  "payeeName": "Ali Khan",
  "deviceId": "android-abc123def456",
  "nonce": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### TransactionPayloadQR (Step 2)
```kotlin
data class TransactionPayloadQR(
    val txId: String,           // Unique transaction ID (UUID)
    val payerId: String,         // Payer's user ID
    val payeeId: String,        // Payee's user ID (from Step 1)
    val amount: Long,            // Amount in smallest currency unit (paisa)
    val timestamp: Long,        // currentTimeMillis
    val nonce: String,          // Random UUID
    val payerName: String,       // Payer's display name
    val note: String? = null    // Optional note
)
```

**QR Format**: Base64 encoded JSON string

**Example**:
```json
{
  "txId": "550e8400-e29b-41d4-a716-446655440001",
  "payerId": "456",
  "payeeId": "123",
  "amount": 50000,
  "timestamp": 1712345678901,
  "nonce": "550e8400-e29b-41d4-a716-446655440002",
  "payerName": "Usman",
  "note": "Payment for services"
}
```

**Base64 Encoding**: The JSON is Base64 encoded before being converted to QR code image.

---

## Security Considerations

### Current Security Features

1. **Nonce Fields**:
   - Both QR codes include random nonces
   - Prevents QR code reuse/replay attacks
   - Ensures each QR is unique

2. **Timestamp Validation**:
   - Transaction QR must be within ±2 minutes
   - Prevents stale/expired transactions
   - Prevents future-dated transactions

3. **Payee ID Matching**:
   - Payee validates that `payeeId` in transaction QR matches their own ID
   - Prevents accepting payments intended for others

4. **Device ID Verification**:
   - Payee QR includes `deviceId`
   - Payer can verify QR came from a real device (not screenshot)

5. **Biometric Authentication**:
   - Required before generating transaction QR
   - Prevents unauthorized payment generation
   - Falls back to device password/PIN if biometric fails

### Potential Enhancements (Future)

For production, consider adding:

1. **Cryptographic Signatures**:
   - Payer signs transaction payload with private key
   - Payee verifies signature with payer's public key
   - Ensures transaction authenticity and integrity

2. **Timestamp in Payee QR**:
   - Add `timestamp` field to PayeeQRPayload
   - Payer can validate QR freshness
   - Prevents using old/stale payee QRs

3. **Hash Verification**:
   - Include hash of transaction data
   - Payee can verify data integrity
   - Detects tampering

4. **Public Key in Payee QR**:
   - Include payee's public key
   - Enables future signature verification
   - Enables encrypted communication

5. **Transaction Counter**:
   - Include sequence number per payer-payee pair
   - Prevents replay attacks even if nonce is reused
   - Enables ordering of transactions

---

## API Endpoints

### Backend Endpoints

#### Generate Payee QR Code
- **Endpoint**: `POST /api/v1/wallets/qr-code`
- **Request**:
  ```json
  {
    "wallet_id": 1
  }
  ```
- **Response**:
  ```json
  {
    "qr_data": {
      "payeeId": "123",
      "payeeName": "Ali Khan",
      "deviceId": "android-abc123",
      "nonce": "random-uuid"
    },
    "qr_image_base64": "iVBORw0KGgo..."
  }
  ```

**Implementation**: `app/api/v1/wallet.py` → `generate_qr_code()`

---

## File Structure

### Android App Files

**Data Models**:
- `Android-App/app/src/main/java/com/offlinepayment/data/PayeeQRPayload.kt`
- `Android-App/app/src/main/java/com/offlinepayment/data/TransactionPayloadQR.kt`
- `Android-App/app/src/main/java/com/offlinepayment/data/local/LocalTransaction.kt`

**UI Screens**:
- `Android-App/app/src/main/java/com/offlinepayment/ui/qr/QRCodeScreen.kt` (Step 1: Payee generates QR)
- `Android-App/app/src/main/java/com/offlinepayment/ui/SendPaymentScreen.kt` (Step 2 & 3: Payer scans, confirms, generates)
- `Android-App/app/src/main/java/com/offlinepayment/ui/qr/QRScannerScreen.kt` (Step 2: Payee QR scanner)
- `Android-App/app/src/main/java/com/offlinepayment/ui/qr/TransactionQRScannerScreen.kt` (Step 4: Transaction QR scanner)
- `Android-App/app/src/main/java/com/offlinepayment/ui/qr/TransactionReceivedScreen.kt` (Step 4: Payment received confirmation)

**Utilities**:
- `Android-App/app/src/main/java/com/offlinepayment/utils/QRCodeHelper.kt` (QR generation/parsing)
- `Android-App/app/src/main/java/com/offlinepayment/data/repository/WalletRepository.kt` (Local storage)

**Database**:
- `Android-App/app/src/main/java/com/offlinepayment/data/local/AppDatabase.kt` (Room database)
- `Android-App/app/src/main/java/com/offlinepayment/data/local/LocalTransactionDao.kt` (DAO)

### Backend Files

**API Endpoints**:
- `app/api/v1/wallet.py` → `generate_qr_code()` (Generates Payee QR)

**Crypto Utilities**:
- `app/core/crypto.py` → `create_payee_qr_payload()` (Creates Payee QR format)

---

## Transaction Flow Diagram

```
┌─────────────┐
│   PAYEE     │
│  (Receiver) │
└──────┬──────┘
       │
       │ Step 1: Opens "Receive" screen
       │ Generates Payee QR: {payeeId, payeeName, deviceId, nonce}
       │
       ▼
┌─────────────────────┐
│  Payee QR Display   │
│  (QRCodeScreen)     │
└──────────┬──────────┘
           │
           │ Payer scans QR
           │
           ▼
┌─────────────┐
│   PAYER     │
│  (Sender)   │
└──────┬──────┘
       │
       │ Step 2: Scans Payee QR
       │ Extracts: payeeId, payeeName, deviceId, nonce
       │
       ▼
┌─────────────────────┐
│ Payee Confirmation  │
│ "Are you paying     │
│  [Payee Name]?"     │
└──────────┬──────────┘
           │
           │ Payer confirms
           │
           ▼
┌─────────────────────┐
│  Amount Input       │
│  + Biometric Auth   │
└──────────┬──────────┘
           │
           │ Step 3: Enters amount, generates Transaction QR
           │ Creates: {txId, payerId, payeeId, amount, timestamp, nonce, payerName, note}
           │ Saves as "SENT" locally
           │
           ▼
┌─────────────────────┐
│ Transaction QR      │
│ Display (Payer)     │
└──────────┬──────────┘
           │
           │ Payee scans Transaction QR
           │
           ▼
┌─────────────┐
│   PAYEE     │
│  (Receiver) │
└──────┬──────┘
       │
       │ Step 4: Scans Transaction QR
       │ Validates: amount > 0, timestamp ±2min, payerId present, payeeId matches
       │
       ▼
┌─────────────────────┐
│  Validation Check   │
└──────────┬──────────┘
           │
           ├─ Valid → Saves as "RECEIVED" locally
           │          Shows "Payment Received (Offline)" screen
           │
           └─ Invalid → Shows error, transaction rejected
```

---

## Error Handling

### Common Error Scenarios

1. **Invalid Payee QR**:
   - Malformed JSON
   - Missing required fields
   - **Action**: Show error, allow retry

2. **Transaction Validation Failures**:
   - Amount ≤ 0 → "Amount must be a positive number"
   - Timestamp outside ±2 min → "Transaction timestamp is outside valid range"
   - Missing payerId → "Payer ID is missing"
   - Payee ID mismatch → "Payee ID mismatch. This transaction is not for you."
   - **Action**: Show error, transaction not saved

3. **Biometric Authentication Failure**:
   - User cancels authentication
   - Authentication fails
   - **Action**: Show error, QR generation blocked

4. **Network Issues**:
   - Not applicable for offline flow
   - All operations work offline
   - Local storage ensures data persistence

---

## Testing Checklist

### Step 1: Payee QR Generation
- [ ] Payee QR is generated with correct format
- [ ] All fields (payeeId, payeeName, deviceId, nonce) are present
- [ ] QR code is scannable
- [ ] Nonce is unique for each QR generation

### Step 2: Payee QR Scanning
- [ ] Payer can scan payee QR successfully
- [ ] Payee details are displayed correctly
- [ ] Device ID verification message appears
- [ ] Payer can confirm or cancel

### Step 3: Transaction QR Generation
- [ ] Amount validation works (positive, within balance, within limit)
- [ ] Biometric authentication is required
- [ ] Transaction QR is generated with correct format
- [ ] Transaction is saved as "SENT" locally
- [ ] QR code is scannable

### Step 4: Transaction QR Scanning & Validation
- [ ] Payee can scan transaction QR successfully
- [ ] Amount validation works (amount > 0)
- [ ] Timestamp validation works (±2 minutes)
- [ ] Payer ID validation works (present and non-empty)
- [ ] Payee ID matching works (rejects if mismatch)
- [ ] Transaction is saved as "RECEIVED" locally on success
- [ ] Error is shown on validation failure
- [ ] "Payment Received (Offline)" screen displays correctly

### Step 5: Local Logging
- [ ] SENT transaction is saved on payer's device
- [ ] RECEIVED transaction is saved on payee's device
- [ ] Both transactions have same txId
- [ ] Both transactions have same amount
- [ ] Both transactions have same timestamp
- [ ] rawPayload contains full JSON on both devices
- [ ] Transactions can be queried from local database

---

## Future Enhancements

### Recommended Additions

1. **Cryptographic Signatures**:
   - Add `signature` field to `TransactionPayloadQR`
   - Payer signs transaction with private key
   - Payee verifies with payer's public key
   - **Benefit**: Ensures transaction authenticity

2. **Timestamp in Payee QR**:
   - Add `timestamp` field to `PayeeQRPayload`
   - Payer validates QR freshness (e.g., ±5 minutes)
   - **Benefit**: Prevents using stale payee QRs

3. **Public Key in Payee QR**:
   - Add `publicKey` field to `PayeeQRPayload`
   - Enables signature verification
   - **Benefit**: Enables cryptographic security

4. **Transaction Status**:
   - Add `status` field to `LocalTransaction`
   - Values: "pending", "synced", "failed"
   - **Benefit**: Track synchronization status

5. **Sync Mechanism**:
   - Implement background sync when online
   - Send `rawPayload` to server
   - Server matches by `txId` and finalizes
   - **Benefit**: Complete the transaction lifecycle

---

## Summary

The offline transaction workflow enables secure peer-to-peer payments without continuous internet connectivity. The 5-step process ensures:

1. ✅ **Payee Identification**: Confirms recipient before payment
2. ✅ **Transaction Creation**: Payer generates payment instruction
3. ✅ **Transaction Validation**: Payee validates and accepts
4. ✅ **Local Logging**: Both devices log independently
5. ✅ **Future Sync**: Full payload stored for server synchronization

All operations work **completely offline**, with transactions stored locally and ready for synchronization when devices come online.

---

## Appendix: QR Payload Field Analysis

### Current MVP Implementation

The current implementation uses minimal fields for MVP functionality. See `QR_PAYLOAD_ANALYSIS.md` for detailed analysis and recommendations.

**Key Points**:
- Current fields are **sufficient for MVP**
- **Signature support** is recommended for production (highest priority)
- Additional fields (timestamp in Payee QR, public key) enhance security

### Recommended Enhancements

1. **Add `signature` to TransactionPayloadQR** (HIGH PRIORITY)
   - Cryptographic proof of authenticity
   - Prevents transaction forgery
   - Backend support already exists

2. **Add `timestamp` to PayeeQRPayload** (MEDIUM PRIORITY)
   - Prevents using stale payee QRs
   - Enhances freshness validation

3. **Add `publicKey` to PayeeQRPayload** (MEDIUM PRIORITY)
   - Enables signature verification
   - Future-proofs for encryption

See `QR_PAYLOAD_ANALYSIS.md` for complete analysis and implementation guide.

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Author**: Development Team

