# Umer's Guide to Work - Offline Payment System Implementation

## Overview

This document provides a comprehensive guide to all the work implemented during this development session. It covers feature workflows, abstract logic, implementation details, and testing requirements.

---

## Table of Contents

1. [Wallet Creation Flow](#1-wallet-creation-flow)
2. [Top-Up Flow](#2-top-up-flow)
3. [Profile Data Management](#3-profile-data-management)
4. [Single Wallet Enforcement](#4-single-wallet-enforcement)
5. [Offline QR Code Generation](#5-offline-qr-code-generation)
6. [Biometric Authentication](#6-biometric-authentication)
7. [Offline Transaction Flow](#7-offline-transaction-flow)
8. [Local Transaction Logging](#8-local-transaction-logging)
9. [Database Migrations](#9-database-migrations)
10. [Testing Checklist](#10-testing-checklist)

---

## 1. Wallet Creation Flow

### Workflow

**Step 1: Initiate Wallet Creation**
- User enters bank account number (no validation - demo purposes)
- App calls `POST /api/v1/wallets/create-request`
- Backend stores bank account number and sends OTP via email
- Email message: "User has initiated wallet creation on this bank account"

**Step 2: Verify and Create Wallet**
- User enters OTP received via email
- App calls `POST /api/v1/wallets/create-verify`
- Backend verifies OTP and creates wallet with provided bank account number
- Wallet is created with `bank_account_number` field (NOT NULL constraint)

**Step 3: Success Feedback**
- App displays success alert when wallet is created
- UI clears the wallet creation form
- Wallet list refreshes to show the new wallet

### Abstract Logic

```
User Input (Bank Account) 
  → API: create-request 
  → Backend: Store bank_account_number, Generate OTP, Send Email
  → User Input (OTP) 
  → API: create-verify 
  → Backend: Verify OTP, Create Wallet
  → Success Alert → UI Reset
```

### Implementation Files

**Backend:**
- `app/api/v1/wallet.py` - `initiate_wallet_creation()`, `verify_and_create_wallet()`
- `app/schemas/wallet.py` - `WalletCreateRequest`, `WalletCreateResponse`, `WalletCreateVerifyRequest`
- `app/models/wallet.py` - `Wallet` model with `bank_account_number` field

**Android:**
- `ui/WalletScreen.kt` - Wallet creation UI with two-step form
- `ui/wallet/WalletViewModel.kt` - `initiateWalletCreation()`, `verifyAndCreateWallet()`
- `data/network/WalletApi.kt` - API interface methods
- `data/repository/WalletRepository.kt` - Repository methods

### Key Features
- ✅ Bank account number stored in database (NOT NULL)
- ✅ OTP sent via email for verification
- ✅ Two-step creation process (request → verify)
- ✅ Success alert and form reset
- ✅ Single wallet per user enforcement

---

## 2. Top-Up Flow

### Workflow

**Step 1: Top-Up Request Form**
- User enters:
  - Amount (must not exceed wallet limit of 5000 PKR)
  - Bank account number
  - User password
- App validates:
  - Amount > 0
  - Amount + current balance ≤ 5000 PKR
  - Bank account number not empty
  - Password not empty
- App calls `POST /api/v1/wallets/top-up`
- Backend sends OTP via email

**Step 2: OTP Verification**
- User enters OTP received via email
- App calls `POST /api/v1/wallets/top-up/verify`
- Backend verifies OTP and processes top-up
- Wallet balance is updated

**Step 3: Success and Refresh**
- App displays success message
- Wallet list refreshes to show updated balance
- User is navigated back to wallet screen

### Abstract Logic

```
User Input (Amount, Bank Account, Password)
  → Validation (Amount limits, Balance check)
  → API: top-up
  → Backend: Validate, Generate OTP, Send Email
  → User Input (OTP)
  → API: top-up/verify
  → Backend: Verify OTP, Update Balance
  → Success → Refresh Wallets
```

### Implementation Files

**Backend:**
- `app/api/v1/wallet.py` - `top_up()`, `verify_top_up()`
- `app/schemas/wallet.py` - `TopUpRequest`, `TopUpVerifyRequest`, `TopUpResponse`

**Android:**
- `ui/TopUpScreen.kt` - Two-step top-up UI (FORM → OTP_VERIFICATION)
- `data/network/WalletApi.kt` - `topUp()`, `verifyTopUp()`
- `data/repository/WalletRepository.kt` - `topUp()`, `verifyTopUp()`
- `utils/WalletLimits.kt` - `MAX_WALLET_BALANCE`, `isTopUpAmountValid()`

### Key Features
- ✅ Two-step top-up process (request → verify)
- ✅ OTP verification for each top-up
- ✅ Amount validation (max 5000 PKR wallet limit)
- ✅ Balance check before top-up
- ✅ Biometric authentication option (if available)

---

## 3. Profile Data Management

### Workflow

**Initial Load:**
1. App checks local Room database (`OfflineUser` table)
2. If user data exists in cache → Display cached data immediately
3. If online → Fetch fresh data from `GET /api/v1/auth/me`
4. Update local cache with fresh data
5. Display updated data

**Automatic Refresh:**
- When app comes to foreground (ON_RESUME lifecycle event)
- Every 30 seconds while app is online and in foreground
- Refresh fetches from API and updates cache

**Offline Access:**
- If offline, app uses cached data from Room database
- No API calls when offline
- Cached data persists across app restarts

### Abstract Logic

```
App Start
  → Load from Cache (Room DB)
  → Display Cached Data (if available)
  → If Online: Fetch from API
  → Update Cache
  → Display Fresh Data
  
Lifecycle: ON_RESUME
  → If Online: Fetch from API
  → Update Cache
  
Periodic Refresh (30s)
  → If Online & Foreground: Fetch from API
  → Update Cache
```

### Implementation Files

**Backend:**
- `app/api/v1/auth.py` - `get_current_user_info()` endpoint
- Returns: `userId`, `email`, `name`, `phone`, `totalBalance`, `offlineBalance`, `qrCodeId`

**Android:**
- `ui/profile/ProfileScreen.kt` - Profile display UI
- `ui/profile/ProfileViewModel.kt` - `loadProfile()`, `refreshProfileSilently()`
- `data/local/OfflineUser.kt` - Room entity for cached user data
- `data/local/OfflineUserDao.kt` - DAO for user data operations
- `data/repository/AuthRepository.kt` - `getCurrentUserInfo()`, `updateCachedUserProfile()`
- `utils/NetworkUtils.kt` - `isOnline()` for network status checking

### Key Features
- ✅ Cache-first approach (offline support)
- ✅ Automatic refresh on resume
- ✅ Periodic refresh (30 seconds)
- ✅ Network-aware (only fetches when online)
- ✅ Displays: name, email, phone, balance, QR code ID

---

## 4. Single Wallet Enforcement

### Workflow

**Backend Enforcement:**
- Before creating a wallet, backend checks if user already has ANY active wallet
- If wallet exists → Returns HTTP 400 error: "User already has a wallet"
- Only one wallet per user is allowed (regardless of wallet type)

**Android UI Updates:**
- `WalletScreen` shows single wallet (not a list)
- Wallet creation form only shown if no wallet exists
- Wallet details displayed if wallet exists

### Abstract Logic

```
Wallet Creation Request
  → Backend: Check existing wallets for user
  → If wallet exists: Return Error
  → If no wallet: Create wallet
  → Return success
```

### Implementation Files

**Backend:**
- `app/api/v1/wallet.py` - `initiate_wallet_creation()`, `verify_and_create_wallet()`, `create_wallet()`
- All methods check: `db.query(Wallet).filter(Wallet.user_id == current_user.id, Wallet.is_active == True).first()`

**Android:**
- `ui/WalletScreen.kt` - Single wallet display logic
- `ui/wallet/WalletViewModel.kt` - `refreshWallets()` handles single wallet

### Key Features
- ✅ Backend prevents multiple wallets per user
- ✅ Android UI reflects single wallet model
- ✅ `/auth/me` endpoint returns single wallet balance

---

## 5. Offline QR Code Generation

### Workflow

**Online Mode:**
1. App fetches wallet private key from `GET /api/v1/wallets/{wallet_id}/private-key`
2. Encrypts private key using AES-256-GCM
3. Stores encrypted key in Room database (`OfflineWallet` table)
4. Uses private key for QR generation

**Offline Mode:**
1. App retrieves encrypted private key from Room database
2. Decrypts private key using AES-256-GCM
3. Uses decrypted key for QR generation
4. No API calls required

**Periodic Refresh:**
- When online, app periodically refreshes cached wallet data
- Updates encrypted private keys if changed
- Updates wallet balance and other metadata

### Abstract Logic

```
Online:
  Fetch Private Key from API
    → Encrypt (AES-256-GCM)
    → Store in Room DB
    → Use for QR Generation

Offline:
  Retrieve from Room DB
    → Decrypt (AES-256-GCM)
    → Use for QR Generation

Periodic Refresh (Online):
  Fetch Latest Data from API
    → Update Cache
```

### Implementation Files

**Backend:**
- `app/api/v1/wallet.py` - `get_wallet_private_key()` endpoint
- Returns encrypted private key for the wallet

**Android:**
- `data/local/OfflineWallet.kt` - Room entity for cached wallet data
- `data/local/OfflineWalletDao.kt` - DAO for wallet cache operations
- `data/repository/WalletRepository.kt` - `getWalletPrivateKey()`, `getCachedPrivateKey()`, `cacheWalletsLocally()`
- `utils/EncryptionHelper.kt` - `encrypt()`, `decrypt()` using AES-256-GCM
- `ui/SendPaymentScreen.kt` - Uses cached data for offline QR generation

### Key Features
- ✅ Works completely offline after initial sync
- ✅ Secure encryption (AES-256-GCM) for private keys
- ✅ Automatic cache refresh when online
- ✅ Fallback to cached data when offline

---

## 6. Biometric Authentication

### Workflow

**Availability Check:**
- App checks if device supports biometric authentication
- Supports: Fingerprint, Face, Iris (BIOMETRIC_STRONG)
- Fallback: Device password/PIN (DEVICE_CREDENTIAL)

**Authentication Flow:**
1. User attempts sensitive operation (QR generation, top-up)
2. App shows biometric prompt
3. User authenticates using:
   - Fingerprint/Face (if available), OR
   - Device password/PIN (fallback)
4. On success → Operation proceeds
5. On failure → Error message shown

**Auto-Trigger:**
- In `SendPaymentScreen`, biometric prompt auto-triggers when:
  - Payee QR is scanned
  - Biometric is available
  - User hasn't authenticated yet

### Abstract Logic

```
Sensitive Operation Triggered
  → Check Biometric Availability
  → Show Biometric Prompt
  → User Authenticates (Biometric or Password/PIN)
  → On Success: Proceed with Operation
  → On Failure: Show Error
```

### Implementation Files

**Android:**
- `utils/BiometricAuthHelper.kt` - `isBiometricAvailable()`, `authenticate()`
- `ui/SendPaymentScreen.kt` - Auto-triggers biometric for QR generation
- `ui/TopUpScreen.kt` - Requires biometric for top-up submission

### Key Features
- ✅ Supports multiple biometric types
- ✅ Device credential fallback (password/PIN)
- ✅ Auto-trigger for QR generation
- ✅ Required for sensitive operations

---

## 7. Offline Transaction Flow

### Complete Workflow (7 Steps - FYP-1 Implementation)

#### **STEP 1: Receiver Generates Identity QR with Dynamic Limits**

**Purpose:** Establish trust and provide transaction capacity information.

**Action:**
- Receiver opens "My QR Code" screen
- App calculates dynamic transaction limit based on receiver's current balance:
  - If balance < 4500 PKR: Max limit = 500 PKR
  - If balance ≥ 4500 PKR: Max limit = 5000 - current balance
- App generates **Payee Identity QR Code** containing:
  ```json
  {
    "payeeId": "unique-user-id",
    "payeeName": "Ali Khan",
    "deviceId": "device-uuid",
    "nonce": "random-uuid",
    "maxTransactionLimit": 240.0
  }
  ```
- **Restriction:** Receiver cannot generate QR if balance >= 5000 PKR
- QR code displayed on receiver's device screen

**Technical Implementation:**
- **File:** `ui/qr/QRCodeScreen.kt`
- **Method:** `QRCodeHelper.createPayeeQR(payeeId, payeeName, deviceId, currentBalance)`
- **Utility:** `WalletLimits.calculateMaxTransactionLimit(currentBalance)`
- **Validation:** Prevents QR generation if balance at max capacity

---

#### **STEP 2: Sender Scans Payee QR**

**Purpose:** Extract payee information and transaction limits.

**Action:**
- Sender opens "Send Payment" screen
- Sender clicks "Scan Payee QR Code" button
- **Restriction:** Button disabled if sender balance <= 0
- Sender scans Receiver's QR code using camera
- App extracts: `payeeId`, `payeeName`, `deviceId`, `nonce`, `maxTransactionLimit`
- App navigates to send payment screen with scanned data

**Technical Implementation:**
- **File:** `ui/qr/ReceiverQRScannerScreen.kt` (in `QRScannerScreen.kt`)
- **Method:** `QRCodeHelper.parsePayeeQR(qrData)`
- **State Management:** Shared state variable `scannedPayeeQRShared` in `MainActivity.kt`
- **Validation:** Checks QR format is valid JSON

---

#### **STEP 3: Payee Confirmation Dialog**

**Purpose:** Confirm payment recipient and show transaction limits.

**Action:**
- **Payee Confirmation Dialog** appears automatically showing:
  - Payee ID
  - Payee Name
  - Device ID
  - **Max Transaction Limit** (from QR code)
- Sender reviews payee information
- Sender clicks:
  - **"Confirm"** → Proceeds to transaction amount form
  - **"Cancel"** → Cancels transaction and returns to send screen

**Technical Implementation:**
- **File:** `ui/SendPaymentScreen.kt`
- **State:** `showPayeeConfirmation` boolean
- **Data:** `scannedPayeeQRFromNav` (PayeeQRPayload)
- **UI:** Material Dialog with payee details and max limit display

---

#### **STEP 4: Transaction Amount Input & Validation**

**Purpose:** Enter and validate transaction amount.

**Action:**
- After payee confirmation, transaction amount form appears
- Sender enters transaction amount
- App validates:
  - Amount > 0
  - Amount ≤ sender's available balance
  - Amount ≤ receiver's max transaction limit (from QR)
  - Sender balance > 0 (enforced at button level)
- User authenticates (biometric or password) before generating QR
- App generates **Transaction Payload QR**:
  ```json
  {
    "txId": "tx-uuid",
    "payerId": "sender-user-id",
    "payeeId": "recipient-id",
    "amount": 24000,  // Amount in paisa
    "timestamp": 1712345678901,
    "nonce": "random-uuid",
    "payerName": "Usman",
    "note": "optional"
  }
  ```
- QR code displayed for receiver to scan
- Instruction: "After receiver scans this QR code, click 'Sent' to confirm payment"

**Technical Implementation:**
- **File:** `ui/SendPaymentScreen.kt`
- **Method:** `QRCodeHelper.createTransactionPayloadQR(...)`
- **Validation:** Dynamic limit from `scannedPayeeQR?.maxTransactionLimit`
- **QR Format:** JSON → Base64 encoded
- **Screen:** Scrollable to ensure "Sent" button is visible

---

#### **STEP 5: Receiver Scans Transaction QR**

**Purpose:** Receive and validate payment transaction.

**Action:**
- Receiver opens "My QR Code" screen
- Receiver clicks "Scan QR" button
- Receiver scans sender's Transaction QR code
- App validates:
  - Amount > 0
  - Timestamp within ±2 minutes
  - `payerId` is present
  - `payeeId` matches THIS device's user ID
- If valid:
  - **Wallet balance updated** (amount added, capped at 5000 PKR)
  - Store transaction locally with status "RECEIVED"
  - Show "Payment Received (Offline)" screen
- If invalid:
  - Show error message
  - Reject transaction

**Technical Implementation:**
- **File:** `ui/qr/TransactionQRScannerScreen.kt`
- **Method:** `QRCodeHelper.parseTransactionPayloadQR()`, `QRCodeHelper.validateTransactionPayload()`
- **Local Storage:** `WalletRepository.saveLocalTransaction()` with `direction = "RECEIVED"`
- **Balance Update:** `WalletRepository.updateOfflineWalletBalance()` - adds amount to receiver balance
- **State Management:** Shared state variable `scannedTransactionPayloadShared` in `MainActivity.kt`

---

#### **STEP 6: Sender Clicks "Sent" Button**

**Purpose:** Finalize transaction and update sender's balance.

**Action:**
- After receiver scans QR, sender clicks **"Sent"** button
- App validates transaction payload exists
- **Wallet balance updated** (amount subtracted from sender)
- Transaction stored locally with status "SENT"
- Transaction marked as completed
- Success message displayed

**Technical Implementation:**
- **File:** `ui/SendPaymentScreen.kt`
- **Button:** "Sent" button (renamed from "OK - Transaction Complete")
- **Local Storage:** `WalletRepository.saveLocalTransaction()` with `direction = "SENT"`
- **Balance Update:** `WalletRepository.updateOfflineWalletBalance()` - subtracts amount from sender balance
- **State:** `transactionCompleted` boolean flag

---

#### **STEP 7: Transaction History Display**

**Purpose:** Display all transactions in history screen.

**Action:**
- User opens "Transactions" screen from navigation drawer
- App loads:
  - **Local transactions** from Room database (offline transactions)
  - **Server transfers** from API (online transfers)
- Transactions displayed with:
  - Direction (SENT/RECEIVED) with color coding
  - Transaction ID
  - Amount (converted from paisa to PKR)
  - Timestamp (formatted)
  - Payer/Payee ID
- Local transactions shown first, then server transfers

**Technical Implementation:**
- **File:** `ui/TransactionListScreen.kt`
- **File:** `MainActivity.kt` - "transactions" composable
- **Methods:** `WalletRepository.getLocalTransactions(userId)`
- **Display:** Combined view of local and server transactions
- **Formatting:** `formatTimestampFromMillis()` for local transactions

---

### Abstract Logic

```
Receiver: Generate Payee QR with Dynamic Limits (Step 1)
  → Calculate Max Transaction Limit
  → Check Balance < 5000 PKR
  → Display QR Code with maxTransactionLimit
  
Sender: Scan Payee QR (Step 2)
  → Parse PayeeQRPayload
  → Check Sender Balance > 0
  → Navigate to Send Screen
  
Sender: Confirm Payee (Step 3)
  → Show Payee Confirmation Dialog
  → Display Max Transaction Limit
  → User Confirms or Cancels
  
Sender: Enter Amount & Generate Transaction QR (Step 4)
  → Validate Amount (≤ balance, ≤ max limit)
  → Authenticate (Biometric)
  → Create TransactionPayloadQR
  → Display QR Code
  → Wait for Receiver to Scan
  
Receiver: Scan Transaction QR (Step 5)
  → Parse TransactionPayloadQR
  → Validate Transaction (timestamp, amount, payeeId)
  → Update Receiver Balance (add amount, cap at 5000)
  → Store Locally (RECEIVED)
  → Show Success Screen
  
Sender: Click "Sent" Button (Step 6)
  → Update Sender Balance (subtract amount)
  → Store Locally (SENT)
  → Mark Transaction Complete
  
Both: Transaction History (Step 7)
  → Load Local Transactions
  → Load Server Transfers
  → Display Combined History
```

### Implementation Files

**Data Models:**
- `data/PayeeQRPayload.kt` - Payee identity QR payload
- `data/TransactionPayloadQR.kt` - Transaction payload QR

**QR Utilities:**
- `utils/QRCodeHelper.kt` - `createPayeeQR()`, `parsePayeeQR()`, `createTransactionPayloadQR()`, `parseTransactionPayloadQR()`, `validateTransactionPayload()`

**UI Screens:**
- `ui/qr/QRCodeScreen.kt` - Payee QR generation
- `ui/qr/ReceiverQRScannerScreen.kt` - Payee QR scanner
- `ui/SendPaymentScreen.kt` - Transaction QR generation
- `ui/qr/TransactionQRScannerScreen.kt` - Transaction QR scanner
- `ui/qr/TransactionReceivedScreen.kt` - Transaction received confirmation

**Local Storage:**
- `data/local/LocalTransaction.kt` - Room entity
- `data/local/LocalTransactionDao.kt` - DAO
- `data/local/AppDatabase.kt` - Database with migration

**Backend:**
- `app/api/v1/wallet.py` - `generate_qr_code()` endpoint (generates Payee QR)
- `app/core/crypto.py` - `create_payee_qr_payload()`

### Key Features
- ✅ 7-step secure transaction flow (FYP-1 complete)
- ✅ Payee identity verification with confirmation dialog
- ✅ Dynamic transaction limit calculation and display
- ✅ Transaction validation (amount, timestamp, payeeId)
- ✅ Automatic wallet balance updates (sender & receiver)
- ✅ Local transaction logging on both devices
- ✅ Transaction history display (local + server)
- ✅ Balance restrictions (receiver max 5000 PKR, sender min 0)
- ✅ Works completely offline
- ✅ Scrollable screens for better UX
- ✅ Shared state management for reliable data passing
- ✅ Ready for future server synchronization

---

## 8. Local Transaction Logging & Balance Updates

### Workflow

**When Sender Clicks "Sent" Button:**
- Transaction stored in Room DB with `direction = "SENT"`
- Contains full transaction payload in `rawPayload` field
- **Sender's wallet balance updated** (amount subtracted)
- Balance update uses `WalletRepository.updateOfflineWalletBalance()`

**When Receiver Scans Transaction QR:**
- Transaction stored in Room DB with `direction = "RECEIVED"`
- Contains full transaction payload in `rawPayload` field
- **Receiver's wallet balance updated** (amount added, capped at 5000 PKR)
- Balance update uses `WalletRepository.updateOfflineWalletBalance()`
- Balance validation ensures receiver doesn't exceed max limit

**Transaction Schema:**
```kotlin
@Entity(tableName = "local_transactions")
data class LocalTransaction(
    @PrimaryKey val txId: String,
    val payerId: String,
    val payeeId: String,
    val amount: Long, // Amount in smallest unit (paisa)
    val timestamp: Long, // Unix timestamp in milliseconds
    val direction: String, // "SENT" or "RECEIVED"
    val rawPayload: String // Full JSON of transaction payload
)
```

### Abstract Logic

```
Transaction Generated/Received
  → Create LocalTransaction Object
  → Store in Room DB
  → Available for:
    - Display in transaction history
    - Future server synchronization
    - Offline transaction management
```

### Implementation Files

**Android:**
- `data/local/LocalTransaction.kt` - Room entity
- `data/local/LocalTransactionDao.kt` - DAO with queries:
  - `getSentTransactions(userId)` - Get all sent transactions
  - `getReceivedTransactions(userId)` - Get all received transactions
  - `getAllTransactionsForUser(userId)` - Get all transactions for user
  - `observeTransactionsForUser(userId)` - Flow for reactive updates
- `data/local/OfflineWalletDao.kt` - DAO with `updateBalance()` method
- `data/repository/WalletRepository.kt` - Repository methods:
  - `saveLocalTransaction()` - Save transaction to local DB
  - `updateOfflineWalletBalance()` - Update wallet balance
  - `getOfflineWalletById()` - Get wallet for balance update
  - `getOfflineWalletByUserIdAndType()` - Get wallet by user and type
  - `getLocalTransactions()` - Get all local transactions
- `data/local/AppDatabase.kt` - Database with `MIGRATION_4_5`
- `ui/TransactionListScreen.kt` - Display local and server transactions
- `MainActivity.kt` - Load and display transactions in "transactions" screen

### Key Features
- ✅ Separate logging for sender and receiver
- ✅ Full payload stored for future sync
- ✅ Automatic balance updates after transactions
- ✅ Balance validation (receiver max 5000 PKR)
- ✅ Query methods for transaction history
- ✅ Combined display of local and server transactions
- ✅ Transaction history visible in "Transactions" screen
- ✅ Reactive Flow support for UI updates

---

## 9. Database Migrations

### Migration Scripts

**Migration 1 → 2:**
- Added `OfflineUser` table for user caching

**Migration 2 → 3:**
- Added `OfflineWallet` table for wallet caching

**Migration 3 → 4:**
- Added `offline_transactions` table (old format)

**Migration 4 → 5:**
- Dropped `offline_transactions` table
- Created `local_transactions` table (new format)
- New schema matches `LocalTransaction` entity

### Backend Database Changes

**Supabase Migration Required:**
- `migrations/002_add_bank_account_number_to_wallets.sql`
- Adds `bank_account_number` column to `wallets` table
- Column is NOT NULL (enforced at database level)

### Implementation Files

**Android:**
- `data/local/AppDatabase.kt` - All migration definitions

**Backend:**
- `migrations/002_add_bank_account_number_to_wallets.sql` - SQL migration script

---

## 10. Testing Checklist

### ✅ Implemented Features (Ready for Testing)

#### **Wallet Creation**
- [ ] Test wallet creation with valid bank account number
- [ ] Test OTP email delivery
- [ ] Test OTP verification with correct code
- [ ] Test OTP verification with incorrect code
- [ ] Test wallet creation success alert
- [ ] Test form reset after successful creation
- [ ] Test preventing multiple wallets per user

#### **Top-Up**
- [ ] Test top-up request with valid amount
- [ ] Test amount validation (max 5000 PKR)
- [ ] Test balance check before top-up
- [ ] Test OTP email delivery for top-up
- [ ] Test OTP verification for top-up
- [ ] Test balance update after successful top-up
- [ ] Test wallet refresh after top-up

#### **Profile Management**
- [ ] Test profile data loading from cache (offline)
- [ ] Test profile data fetching from API (online)
- [ ] Test automatic refresh on app resume
- [ ] Test periodic refresh (30 seconds)
- [ ] Test profile display (name, email, phone, balance, QR code ID)
- [ ] Test cache persistence across app restarts

#### **Offline QR Generation**
- [ ] Test QR generation while online (fetches from API)
- [ ] Test QR generation while offline (uses cache)
- [ ] Test private key encryption/decryption
- [ ] Test cache refresh when coming online
- [ ] Test QR code format (Payee QR and Transaction QR)

#### **Biometric Authentication**
- [ ] Test biometric prompt display
- [ ] Test fingerprint authentication
- [ ] Test face authentication (if available)
- [ ] Test device password/PIN fallback
- [ ] Test authentication failure handling
- [ ] Test auto-trigger in SendPaymentScreen

#### **Offline Transaction Flow**
- [ ] **Step 1:** Test Payee QR generation
- [ ] **Step 2:** Test Payee QR scanning and parsing
- [ ] **Step 2:** Test payee confirmation screen
- [ ] **Step 3:** Test transaction QR generation
- [ ] **Step 3:** Test amount validation
- [ ] **Step 3:** Test transaction storage (SENT)
- [ ] **Step 4:** Test transaction QR scanning
- [ ] **Step 4:** Test transaction validation (amount, timestamp, payeeId)
- [ ] **Step 4:** Test transaction storage (RECEIVED)
- [ ] **Step 5:** Test local transaction logging on both devices
- [ ] Test transaction history queries (sent/received)

#### **Local Transaction Storage**
- [ ] Test saving SENT transactions
- [ ] Test saving RECEIVED transactions
- [ ] Test querying sent transactions
- [ ] Test querying received transactions
- [ ] Test querying all transactions for user
- [ ] Test transaction data persistence

#### **Database Migrations**
- [ ] Test Room database migration from version 4 to 5
- [ ] Test Supabase migration (bank_account_number column)
- [ ] Test data integrity after migrations

### 🔄 Integration Testing

- [ ] Test complete wallet creation → top-up → send payment flow
- [ ] Test offline transaction end-to-end (both devices)
- [ ] Test online/offline mode switching
- [ ] Test app restart with cached data
- [ ] Test multiple users on same device (if applicable)

### 🐛 Edge Cases to Test

- [ ] Test with invalid OTP codes
- [ ] Test with expired OTP codes
- [ ] Test with network interruptions during API calls
- [ ] Test with invalid QR codes
- [ ] Test with expired transaction timestamps (>2 minutes)
- [ ] Test with mismatched payeeId in transaction QR
- [ ] Test with insufficient balance
- [ ] Test with amount exceeding transaction limit (500 PKR)
- [ ] Test with amount exceeding wallet limit (5000 PKR)
- [ ] Test biometric authentication cancellation
- [ ] Test with null userId scenarios

### 📱 Device Testing

- [ ] Test on devices with fingerprint sensor
- [ ] Test on devices with face recognition
- [ ] Test on devices without biometric (password/PIN fallback)
- [ ] Test on devices with different Android versions
- [ ] Test camera permissions for QR scanning
- [ ] Test offline mode (airplane mode)

### 🔒 Security Testing

- [ ] Test private key encryption strength
- [ ] Test transaction payload validation
- [ ] Test timestamp validation (replay attack prevention)
- [ ] Test payeeId validation (prevents wrong recipient)
- [ ] Test nonce uniqueness

---

## 11. Documentation Created/Updated

### Files Created/Updated

1. **Transaction_flow_FYP_1.md** (NEW)
   - Complete FYP-1 scope and deliverables
   - 7-step transaction workflow documentation
   - Technical implementation details
   - Temporary limitations
   - FYP-2 planned features

2. **SERVER_DOCUMENTATION.md** (NEW)
   - Complete API endpoints documentation (30+ endpoints)
   - Database schema with SQL definitions
   - Database migrations approach
   - Third-party services (SendGrid, SMTP, Resend)
   - Security features
   - Configuration details

3. **API_DOCUMENTATION.md** (Updated)
   - Added wallet creation endpoints (`create-request`, `create-verify`)
   - Added wallet top-up endpoints (`topup`, `topup/verify`)
   - Updated endpoint numbering
   - Added email service information

4. **Android-App/README.md** (Updated)
   - Current features (FYP-1 completion status)
   - Updated project structure
   - Important files with purposes
   - Architecture details
   - Security implementation
   - Recent changes log

5. **OFFLINE_TRANSACTION_WORKFLOW.md**
   - Complete transaction workflow documentation
   - Technical implementation details
   - Security features
   - Future enhancements

6. **QR_PAYLOAD_ANALYSIS.md**
   - Analysis of QR code payload fields
   - Current MVP fields
   - Recommendations for production

7. **README.md** (Updated)
   - Added links to new documentation files

8. **START_HERE.md** (Updated)
   - Added entries for new documentation
   - Updated learning paths

9. **DOCUMENTATION_INDEX.md** (Updated)
   - Added references to new documentation

---

## 12. Code Quality Improvements & Bug Fixes

### Fixed Issues

1. ✅ Removed hardcoded `userId = 1` fallback
2. ✅ Implemented proper error handling for null userId
3. ✅ Fixed suspend function calls in MainActivity
4. ✅ Fixed smart cast issues
5. ✅ Fixed Result type mismatches in WalletRepository
6. ✅ Added missing imports
7. ✅ Fixed missing closing braces
8. ✅ Resolved function overload conflicts
9. ✅ **Fixed login race condition** - Explicitly set `isLoggedIn = true` on successful login
10. ✅ **Fixed "login failed" flash** - Added minimum 500ms delay before showing errors
11. ✅ **Fixed blank screen after scanning payee QR** - Replaced `SavedStateHandle` with shared state
12. ✅ **Fixed receiver transaction QR crash** - Used shared state for `TransactionPayloadQR`
13. ✅ **Fixed duplicate context declaration** - Removed redundant context variable
14. ✅ **Fixed "Sent" button visibility** - Made `SendPaymentScreen` scrollable
15. ✅ **Fixed transaction balance updates** - Implemented automatic balance updates for sender and receiver
16. ✅ **Fixed transaction history** - Added local transaction loading and display

### Architecture Improvements

1. ✅ Consistent use of local variables to avoid smart cast issues
2. ✅ Proper coroutine usage for suspend functions
3. ✅ Type-safe userId handling (no fallback values)
4. ✅ Clean separation of concerns (Repository pattern)
5. ✅ Proper error handling and user feedback
6. ✅ **Shared state management** - Replaced `SavedStateHandle` with `mutableStateOf` for reliable data passing
7. ✅ **Multiple observation methods** - Using immediate checks, `LaunchedEffect`, and navigation state for data availability
8. ✅ **Balance update methods** - Added `updateBalance()` to `OfflineWalletDao` and repository methods
9. ✅ **Transaction history integration** - Combined local and server transactions in single view
10. ✅ **Scrollable UI** - Made screens scrollable for better UX

---

## 13. API Endpoints Used

### Authentication
- `GET /api/v1/auth/me` - Get current user info

### Wallet Management
- `POST /api/v1/wallets/create-request` - Initiate wallet creation
- `POST /api/v1/wallets/create-verify` - Verify and create wallet
- `GET /api/v1/wallets` - List wallets
- `GET /api/v1/wallets/{wallet_id}` - Get wallet details
- `GET /api/v1/wallets/{wallet_id}/private-key` - Get wallet private key
- `POST /api/v1/wallets/qr-code` - Generate Payee QR code
- `POST /api/v1/wallets/topup` - Request top-up (sends OTP)
- `POST /api/v1/wallets/topup/verify` - Verify top-up and update balance
- `POST /api/v1/wallets/transfer` - Transfer funds between wallets
- `GET /api/v1/wallets/transfers/history` - Get transfer history

---

## 14. Summary of Changes

### Backend Changes
- Added `bank_account_number` field to `Wallet` model (NOT NULL)
- Created two-step wallet creation endpoints
- Created two-step top-up endpoints
- Updated `/auth/me` endpoint to return single wallet balance
- Added wallet private key endpoint
- Updated QR code generation to use Payee QR format
- Added single wallet enforcement logic

### Android Changes
- Implemented wallet creation UI with OTP verification
- Implemented top-up UI with OTP verification
- Implemented profile data fetching and caching
- Implemented automatic profile refresh
- Implemented offline QR generation with encryption
- Implemented biometric authentication with fallback
- Implemented complete offline transaction flow (7 steps)
- Implemented payee confirmation dialog with dynamic limits
- Implemented transaction amount validation with dynamic limits
- Implemented automatic wallet balance updates (sender & receiver)
- Implemented local transaction logging (SENT/RECEIVED)
- Implemented transaction history display (local + server)
- Added Room database migrations
- Updated all QR code handling to new formats
- Fixed multiple compilation errors and type issues
- Fixed login race condition and error display timing
- Fixed blank screen issues after QR scanning
- Fixed transaction QR crash on receiver side
- Made screens scrollable for better UX
- Implemented shared state management for reliable data passing

### Database Changes
- Added `bank_account_number` column to `wallets` table (NOT NULL)
- Created `local_transactions` table in Room database
- Migrated from old `offline_transactions` to new `local_transactions`
- Added `updateBalance()` method to `OfflineWalletDao` for balance updates
- Added `maxTransactionLimit` field to `PayeeQRPayload` (Parcelable)

---

## 15. Next Steps

### Immediate Testing
1. Test all implemented features according to the checklist above
2. Verify database migrations work correctly
3. Test offline/online mode switching
4. Test end-to-end transaction flow

### Future Enhancements (FYP-2)
1. **BLE Integration**
   - Bluetooth Low Energy proximity detection
   - BLE acknowledgment handshake
   - Automatic transaction finalization
   - Two-phase commit system

2. **Cryptographic Enhancements**
   - Transaction payload signatures
   - Signature verification
   - Hash-chained local ledger
   - Tamper-proof transaction records

3. **Advanced Security**
   - Certificate pinning for API calls
   - Enhanced key storage (Android Keystore)
   - Key rotation mechanism
   - Replay-prevention engine

4. **Sync Features**
   - Automatic server synchronization
   - Conflict resolution
   - Transaction reconciliation
   - Deferred sync protocol

5. **Additional Features**
   - Multi-currency support
   - Enhanced transaction receipts
   - Push notifications for transactions
   - Transaction dispute resolution

---

## Notes

- All wallet operations require authentication (JWT token)
- Private keys are encrypted using AES-256-GCM before storage
- Transaction timestamps validated within ±2 minutes
- Maximum wallet balance: 5000 PKR (enforced)
- Maximum transaction amount: Dynamic based on receiver's balance
- Each user can have only one wallet
- All offline transactions logged locally for future sync
- Wallet balances automatically updated after successful transactions
- Sender cannot send if balance is 0
- Receiver cannot generate QR if balance >= 5000 PKR
- Transaction history displays both local and server transactions
- Shared state management used for reliable data passing between screens
- Minimum 500ms delay before showing login errors (prevents confusion)

### FYP-1 Status: ✅ COMPLETE

All core features for FYP-1 have been implemented:
- ✅ Complete offline transaction flow (7 steps)
- ✅ QR code generation and scanning
- ✅ Local transaction storage
- ✅ Automatic balance updates
- ✅ Transaction history display
- ✅ Dynamic transaction limits
- ✅ Payee confirmation dialog
- ✅ All bug fixes and improvements

### FYP-2 Planning: 🚧 IN PROGRESS

Planning phase for production-grade enhancements:
- BLE integration
- Cryptographic signing
- Hash-chained ledger
- Automatic synchronization

---

**Document Version:** 2.0  
**Last Updated:** December 2025  
**Author:** Development Session Documentation  
**Status:** FYP-1 Complete, FYP-2 Planning

