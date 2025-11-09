# Mobile App Implementation Guide

## Overview

This guide provides detailed instructions for implementing the Android mobile application for the Offline Payment System. The mobile app is the client-side component that enables users to perform offline transactions.

---

## Architecture

### Components

```
┌─────────────────────────────────────────┐
│         Android Application             │
├─────────────────────────────────────────┤
│  UI Layer (Jetpack Compose/XML)         │
│  ├── Login/Signup                       │
│  ├── Wallet Management                  │
│  ├── QR Scanner                         │
│  ├── Transaction History                │
│  └── Settings                           │
├─────────────────────────────────────────┤
│  Business Logic Layer                   │
│  ├── Authentication Manager             │
│  ├── Wallet Manager                     │
│  ├── Transaction Manager                │
│  ├── Crypto Manager (RSA)               │
│  └── Sync Manager                       │
├─────────────────────────────────────────┤
│  Data Layer                             │
│  ├── Local Database (Room/SQLite)       │
│  ├── Shared Preferences (Encrypted)     │
│  ├── Android Keystore (Keys)            │
│  └── API Client (Retrofit)              │
├─────────────────────────────────────────┤
│  Security Layer                         │
│  ├── Biometric Authentication           │
│  ├── Certificate Pinning                │
│  ├── Root Detection                     │
│  └── Code Obfuscation (ProGuard)        │
└─────────────────────────────────────────┘
```

---

## Technology Stack

### Recommended Technologies

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Kotlin | 1.9+ |
| UI Framework | Jetpack Compose | Latest |
| Architecture | MVVM + Clean Architecture | - |
| Dependency Injection | Hilt/Dagger | Latest |
| Networking | Retrofit + OkHttp | 2.9+ |
| Database | Room | 2.5+ |
| Cryptography | Android Keystore + BouncyCastle | - |
| QR Code | ZXing | 3.5+ |
| Biometric | AndroidX Biometric | 1.1+ |
| Coroutines | Kotlin Coroutines | 1.7+ |

---

## Project Structure

```
app/
├── src/
│   ├── main/
│   │   ├── java/com/offlinepay/
│   │   │   ├── data/
│   │   │   │   ├── local/
│   │   │   │   │   ├── dao/
│   │   │   │   │   │   ├── WalletDao.kt
│   │   │   │   │   │   ├── TransactionDao.kt
│   │   │   │   │   │   └── UserDao.kt
│   │   │   │   │   ├── entities/
│   │   │   │   │   │   ├── WalletEntity.kt
│   │   │   │   │   │   ├── TransactionEntity.kt
│   │   │   │   │   │   └── UserEntity.kt
│   │   │   │   │   └── AppDatabase.kt
│   │   │   │   ├── remote/
│   │   │   │   │   ├── api/
│   │   │   │   │   │   ├── AuthApi.kt
│   │   │   │   │   │   ├── WalletApi.kt
│   │   │   │   │   │   └── TransactionApi.kt
│   │   │   │   │   ├── dto/
│   │   │   │   │   │   ├── LoginRequest.kt
│   │   │   │   │   │   ├── WalletResponse.kt
│   │   │   │   │   │   └── TransactionDto.kt
│   │   │   │   │   └── ApiClient.kt
│   │   │   │   └── repository/
│   │   │   │       ├── AuthRepository.kt
│   │   │   │       ├── WalletRepository.kt
│   │   │   │       └── TransactionRepository.kt
│   │   │   ├── domain/
│   │   │   │   ├── model/
│   │   │   │   │   ├── Wallet.kt
│   │   │   │   │   ├── Transaction.kt
│   │   │   │   │   └── User.kt
│   │   │   │   ├── usecase/
│   │   │   │   │   ├── CreateOfflineTransactionUseCase.kt
│   │   │   │   │   ├── SyncTransactionsUseCase.kt
│   │   │   │   │   └── GenerateQRCodeUseCase.kt
│   │   │   │   └── repository/
│   │   │   │       └── (Repository Interfaces)
│   │   │   ├── presentation/
│   │   │   │   ├── auth/
│   │   │   │   │   ├── LoginScreen.kt
│   │   │   │   │   ├── LoginViewModel.kt
│   │   │   │   │   └── SignupScreen.kt
│   │   │   │   ├── wallet/
│   │   │   │   │   ├── WalletScreen.kt
│   │   │   │   │   ├── WalletViewModel.kt
│   │   │   │   │   └── CreateWalletScreen.kt
│   │   │   │   ├── transaction/
│   │   │   │   │   ├── TransactionScreen.kt
│   │   │   │   │   ├── TransactionViewModel.kt
│   │   │   │   │   └── QRScannerScreen.kt
│   │   │   │   └── MainActivity.kt
│   │   │   ├── security/
│   │   │   │   ├── CryptoManager.kt
│   │   │   │   ├── KeystoreManager.kt
│   │   │   │   ├── BiometricManager.kt
│   │   │   │   └── CertificatePinner.kt
│   │   │   └── util/
│   │   │       ├── NetworkMonitor.kt
│   │   │       ├── Constants.kt
│   │   │       └── Extensions.kt
│   │   ├── res/
│   │   └── AndroidManifest.xml
│   └── test/
└── build.gradle
```

---

## Implementation Steps

### Phase 1: Setup & Authentication (Week 1-2)

#### 1.1 Project Setup

**build.gradle (Project)**:
```gradle
buildscript {
    ext.kotlin_version = "1.9.0"
    dependencies {
        classpath "com.android.tools.build:gradle:8.1.0"
        classpath "org.jetbrains.kotlin:kotlin-gradle-plugin:$kotlin_version"
        classpath "com.google.dagger:hilt-android-gradle-plugin:2.48"
    }
}
```

**build.gradle (App)**:
```gradle
plugins {
    id 'com.android.application'
    id 'kotlin-android'
    id 'kotlin-kapt'
    id 'dagger.hilt.android.plugin'
}

android {
    compileSdk 34
    
    defaultConfig {
        applicationId "com.offlinepay.app"
        minSdk 26
        targetSdk 34
        versionCode 1
        versionName "1.0.0"
    }
    
    buildFeatures {
        compose true
    }
    
    composeOptions {
        kotlinCompilerExtensionVersion "1.5.0"
    }
}

dependencies {
    // Kotlin
    implementation "org.jetbrains.kotlin:kotlin-stdlib:$kotlin_version"
    implementation "org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3"
    
    // Jetpack Compose
    implementation "androidx.compose.ui:ui:1.5.0"
    implementation "androidx.compose.material3:material3:1.1.1"
    implementation "androidx.compose.ui:ui-tooling-preview:1.5.0"
    implementation "androidx.activity:activity-compose:1.7.2"
    
    // Hilt
    implementation "com.google.dagger:hilt-android:2.48"
    kapt "com.google.dagger:hilt-compiler:2.48"
    
    // Retrofit
    implementation "com.squareup.retrofit2:retrofit:2.9.0"
    implementation "com.squareup.retrofit2:converter-gson:2.9.0"
    implementation "com.squareup.okhttp3:logging-interceptor:4.11.0"
    
    // Room
    implementation "androidx.room:room-runtime:2.5.2"
    implementation "androidx.room:room-ktx:2.5.2"
    kapt "androidx.room:room-compiler:2.5.2"
    
    // Cryptography
    implementation "androidx.security:security-crypto:1.1.0-alpha06"
    implementation "org.bouncycastle:bcprov-jdk15on:1.70"
    
    // QR Code
    implementation "com.google.zxing:core:3.5.1"
    implementation "com.journeyapps:zxing-android-embedded:4.3.0"
    
    // Biometric
    implementation "androidx.biometric:biometric:1.1.0"
    
    // DataStore
    implementation "androidx.datastore:datastore-preferences:1.0.0"
}
```

#### 1.2 Network Layer

**ApiClient.kt**:
```kotlin
object ApiClient {
    private const val BASE_URL = "https://api.offlinepay.pk/"
    
    private val certificatePinner = CertificatePinner.Builder()
        .add("api.offlinepay.pk", "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
        .build()
    
    private val okHttpClient = OkHttpClient.Builder()
        .certificatePinner(certificatePinner)
        .addInterceptor(AuthInterceptor())
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BODY 
                    else HttpLoggingInterceptor.Level.NONE
        })
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()
    
    val retrofit: Retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
}
```

**AuthApi.kt**:
```kotlin
interface AuthApi {
    @POST("auth/signup")
    suspend fun signup(@Body request: SignupRequest): SignupResponse
    
    @POST("auth/verify-email")
    suspend fun verifyEmail(@Body request: VerifyEmailRequest): MessageResponse
    
    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse
    
    @POST("auth/login/confirm")
    suspend fun confirmLogin(@Body request: ConfirmLoginRequest): TokenResponse
    
    @POST("auth/token/refresh")
    suspend fun refreshToken(@Body request: RefreshTokenRequest): TokenResponse
    
    @POST("auth/logout")
    suspend fun logout(@Body request: LogoutRequest): MessageResponse
}
```

#### 1.3 Local Database

**AppDatabase.kt**:
```kotlin
@Database(
    entities = [
        UserEntity::class,
        WalletEntity::class,
        TransactionEntity::class
    ],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun userDao(): UserDao
    abstract fun walletDao(): WalletDao
    abstract fun transactionDao(): TransactionDao
    
    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null
        
        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "offline_pay_db"
                )
                .fallbackToDestructiveMigration()
                .build()
                INSTANCE = instance
                instance
            }
        }
    }
}
```

**TransactionEntity.kt**:
```kotlin
@Entity(tableName = "transactions")
data class TransactionEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val senderWalletId: Long,
    val receiverPublicKey: String,
    val amount: Double,
    val currency: String,
    val nonce: String,
    val signature: String,
    val receiptHash: String,
    val receiptData: String,
    val status: String, // pending, synced, confirmed
    val createdAt: Long,
    val syncedAt: Long? = null
)
```

---

### Phase 2: Cryptography Implementation (Week 3)

#### 2.1 Keystore Manager

**KeystoreManager.kt**:
```kotlin
class KeystoreManager(private val context: Context) {
    private val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    
    fun generateKeyPair(alias: String): KeyPair {
        if (keyStore.containsAlias(alias)) {
            return getKeyPair(alias)
        }
        
        val keyPairGenerator = KeyPairGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_RSA,
            "AndroidKeyStore"
        )
        
        val parameterSpec = KeyGenParameterSpec.Builder(
            alias,
            KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
        ).apply {
            setKeySize(2048)
            setDigests(KeyProperties.DIGEST_SHA256)
            setSignaturePaddings(KeyProperties.SIGNATURE_PADDING_RSA_PSS)
            setUserAuthenticationRequired(true)
            setUserAuthenticationValidityDurationSeconds(30)
        }.build()
        
        keyPairGenerator.initialize(parameterSpec)
        return keyPairGenerator.generateKeyPair()
    }
    
    fun getKeyPair(alias: String): KeyPair {
        val privateKey = keyStore.getKey(alias, null) as PrivateKey
        val publicKey = keyStore.getCertificate(alias).publicKey
        return KeyPair(publicKey, privateKey)
    }
    
    fun getPublicKeyPEM(alias: String): String {
        val publicKey = keyStore.getCertificate(alias).publicKey
        val encoded = Base64.encodeToString(publicKey.encoded, Base64.NO_WRAP)
        return "-----BEGIN PUBLIC KEY-----\n$encoded\n-----END PUBLIC KEY-----"
    }
    
    fun deleteKeyPair(alias: String) {
        if (keyStore.containsAlias(alias)) {
            keyStore.deleteEntry(alias)
        }
    }
}
```

#### 2.2 Crypto Manager

**CryptoManager.kt**:
```kotlin
class CryptoManager(private val keystoreManager: KeystoreManager) {
    
    fun signTransaction(transactionData: Map<String, Any>, keyAlias: String): String {
        val keyPair = keystoreManager.getKeyPair(keyAlias)
        val signature = Signature.getInstance("SHA256withRSA/PSS").apply {
            initSign(keyPair.private)
            update(canonicalJson(transactionData).toByteArray())
        }
        return Base64.encodeToString(signature.sign(), Base64.NO_WRAP)
    }
    
    fun verifySignature(
        transactionData: Map<String, Any>,
        signatureB64: String,
        publicKeyPEM: String
    ): Boolean {
        return try {
            val publicKey = loadPublicKeyFromPEM(publicKeyPEM)
            val signature = Signature.getInstance("SHA256withRSA/PSS").apply {
                initVerify(publicKey)
                update(canonicalJson(transactionData).toByteArray())
            }
            signature.verify(Base64.decode(signatureB64, Base64.NO_WRAP))
        } catch (e: Exception) {
            false
        }
    }
    
    fun generateNonce(): String {
        val random = SecureRandom()
        val bytes = ByteArray(32)
        random.nextBytes(bytes)
        return bytes.joinToString("") { "%02x".format(it) }
    }
    
    fun hashReceipt(receiptData: Map<String, Any>): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val hash = digest.digest(canonicalJson(receiptData).toByteArray())
        return hash.joinToString("") { "%02x".format(it) }
    }
    
    private fun canonicalJson(data: Map<String, Any>): String {
        return Gson().toJson(data.toSortedMap())
    }
    
    private fun loadPublicKeyFromPEM(pem: String): PublicKey {
        val publicKeyPEM = pem
            .replace("-----BEGIN PUBLIC KEY-----", "")
            .replace("-----END PUBLIC KEY-----", "")
            .replace("\\s".toRegex(), "")
        
        val decoded = Base64.decode(publicKeyPEM, Base64.NO_WRAP)
        val keySpec = X509EncodedKeySpec(decoded)
        val keyFactory = KeyFactory.getInstance("RSA")
        return keyFactory.generatePublic(keySpec)
    }
}
```

---

### Phase 3: Offline Transaction Flow (Week 4-5)

#### 3.1 QR Code Scanner

**QRScannerScreen.kt**:
```kotlin
@Composable
fun QRScannerScreen(
    onQRCodeScanned: (String) -> Unit,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val cameraProviderFuture = remember { ProcessCameraProvider.getInstance(context) }
    
    AndroidView(
        factory = { ctx ->
            val previewView = PreviewView(ctx)
            val cameraProvider = cameraProviderFuture.get()
            
            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(previewView.surfaceProvider)
            }
            
            val imageAnalyzer = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
                .also {
                    it.setAnalyzer(
                        ContextCompat.getMainExecutor(ctx),
                        QRCodeAnalyzer { qrCode ->
                            onQRCodeScanned(qrCode)
                        }
                    )
                }
            
            val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA
            
            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    ctx as LifecycleOwner,
                    cameraSelector,
                    preview,
                    imageAnalyzer
                )
            } catch (e: Exception) {
                Log.e("QRScanner", "Camera binding failed", e)
            }
            
            previewView
        },
        modifier = Modifier.fillMaxSize()
    )
}

class QRCodeAnalyzer(private val onQRCodeDetected: (String) -> Unit) : ImageAnalysis.Analyzer {
    private val reader = MultiFormatReader().apply {
        setHints(mapOf(DecodeHintType.POSSIBLE_FORMATS to listOf(BarcodeFormat.QR_CODE)))
    }
    
    override fun analyze(imageProxy: ImageProxy) {
        // QR code detection logic using ZXing
        // Convert ImageProxy to bitmap and decode
    }
}
```

#### 3.2 Create Offline Transaction

**CreateOfflineTransactionUseCase.kt**:
```kotlin
class CreateOfflineTransactionUseCase @Inject constructor(
    private val transactionRepository: TransactionRepository,
    private val walletRepository: WalletRepository,
    private val cryptoManager: CryptoManager,
    private val keystoreManager: KeystoreManager
) {
    suspend operator fun invoke(
        senderWalletId: Long,
        receiverQRData: QRCodeData,
        amount: Double,
        currency: String
    ): Result<TransactionReceipt> = withContext(Dispatchers.IO) {
        try {
            // 1. Validate sender wallet and balance
            val senderWallet = walletRepository.getWalletById(senderWalletId)
                ?: return@withContext Result.failure(Exception("Wallet not found"))
            
            if (senderWallet.balance < amount) {
                return@withContext Result.failure(Exception("Insufficient balance"))
            }
            
            // 2. Generate nonce
            val nonce = cryptoManager.generateNonce()
            
            // 3. Create transaction data
            val transactionData = mapOf(
                "sender_wallet_id" to senderWalletId,
                "receiver_public_key" to receiverQRData.publicKey,
                "receiver_user_id" to receiverQRData.userId,
                "receiver_wallet_id" to receiverQRData.walletId,
                "amount" to amount.toString(),
                "currency" to currency,
                "nonce" to nonce,
                "timestamp" to System.currentTimeMillis()
            )
            
            // 4. Sign transaction with private key
            val signature = cryptoManager.signTransaction(
                transactionData,
                "wallet_${senderWalletId}_key"
            )
            
            // 5. Create receipt
            val receipt = createReceipt(transactionData, signature)
            
            // 6. Update local wallet balance
            walletRepository.updateBalance(senderWalletId, senderWallet.balance - amount)
            
            // 7. Store transaction locally
            val transaction = TransactionEntity(
                senderWalletId = senderWalletId,
                receiverPublicKey = receiverQRData.publicKey,
                amount = amount,
                currency = currency,
                nonce = nonce,
                signature = signature,
                receiptHash = receipt.receiptHash,
                receiptData = Gson().toJson(receipt),
                status = "pending",
                createdAt = System.currentTimeMillis()
            )
            transactionRepository.insertTransaction(transaction)
            
            Result.success(receipt)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    private fun createReceipt(
        transactionData: Map<String, Any>,
        signature: String
    ): TransactionReceipt {
        val receipt = TransactionReceipt(
            version = "1.0",
            type = "offline_payment_receipt",
            senderWalletId = transactionData["sender_wallet_id"] as Long,
            receiverPublicKey = transactionData["receiver_public_key"] as String,
            amount = transactionData["amount"] as String,
            currency = transactionData["currency"] as String,
            nonce = transactionData["nonce"] as String,
            signature = signature,
            timestamp = transactionData["timestamp"] as Long
        )
        receipt.receiptHash = cryptoManager.hashReceipt(receipt.toMap())
        return receipt
    }
}
```

---

### Phase 4: Synchronization (Week 6)

#### 4.1 Sync Manager

**SyncManager.kt**:
```kotlin
class SyncManager @Inject constructor(
    private val transactionRepository: TransactionRepository,
    private val transactionApi: TransactionApi,
    private val networkMonitor: NetworkMonitor
) {
    suspend fun syncPendingTransactions(): Result<SyncResult> = withContext(Dispatchers.IO) {
        try {
            if (!networkMonitor.isOnline()) {
                return@withContext Result.failure(Exception("No internet connection"))
            }
            
            // Get all pending transactions
            val pendingTransactions = transactionRepository.getPendingTransactions()
            
            if (pendingTransactions.isEmpty()) {
                return@withContext Result.success(SyncResult(0, 0))
            }
            
            // Prepare sync request
            val syncRequest = SyncRequest(
                transactions = pendingTransactions.map { it.toDto() }
            )
            
            // Send to server
            val response = transactionApi.syncTransactions(syncRequest)
            
            // Update local database
            response.synced.forEach { syncedTx ->
                transactionRepository.updateTransactionStatus(
                    syncedTx.nonce,
                    "synced",
                    System.currentTimeMillis()
                )
            }
            
            Result.success(SyncResult(
                synced = response.totalSynced,
                failed = response.totalFailed
            ))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    fun startAutoSync() {
        // Start periodic background sync using WorkManager
        val syncWorkRequest = PeriodicWorkRequestBuilder<SyncWorker>(
            15, TimeUnit.MINUTES
        ).setConstraints(
            Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
        ).build()
        
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            "transaction_sync",
            ExistingPeriodicWorkPolicy.KEEP,
            syncWorkRequest
        )
    }
}
```

---

### Phase 5: Security Hardening (Week 7)

#### 5.1 Root Detection

```kotlin
object RootDetection {
    fun isDeviceRooted(): Boolean {
        return checkRootMethod1() || checkRootMethod2() || checkRootMethod3()
    }
    
    private fun checkRootMethod1(): Boolean {
        val buildTags = Build.TAGS
        return buildTags != null && buildTags.contains("test-keys")
    }
    
    private fun checkRootMethod2(): Boolean {
        val paths = arrayOf(
            "/system/app/Superuser.apk",
            "/sbin/su",
            "/system/bin/su",
            "/system/xbin/su",
            "/data/local/xbin/su",
            "/data/local/bin/su",
            "/system/sd/xbin/su",
            "/system/bin/failsafe/su",
            "/data/local/su"
        )
        return paths.any { File(it).exists() }
    }
    
    private fun checkRootMethod3(): Boolean {
        return try {
            Runtime.getRuntime().exec("su")
            true
        } catch (e: Exception) {
            false
        }
    }
}
```

#### 5.2 Biometric Authentication

```kotlin
class BiometricAuthManager(private val activity: FragmentActivity) {
    private val executor = ContextCompat.getMainExecutor(activity)
    private val biometricPrompt = BiometricPrompt(
        activity,
        executor,
        object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                // Authentication successful
            }
            
            override fun onAuthenticationFailed() {
                // Authentication failed
            }
            
            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                // Authentication error
            }
        }
    )
    
    fun authenticate(onSuccess: () -> Unit, onError: (String) -> Unit) {
        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle("Biometric Authentication")
            .setSubtitle("Authenticate to access your wallet")
            .setNegativeButtonText("Cancel")
            .build()
        
        biometricPrompt.authenticate(promptInfo)
    }
}
```

---

## Testing Strategy

### Unit Tests
- Cryptography functions
- Transaction validation
- Balance calculations
- Nonce generation

### Integration Tests
- API communication
- Database operations
- Sync mechanism

### UI Tests
- User flows (Espresso/Compose Testing)
- QR code scanning
- Transaction creation

### Security Tests
- Root detection
- Certificate pinning
- Key storage
- Biometric authentication

---

## Deployment Checklist

- [ ] Enable ProGuard/R8 obfuscation
- [ ] Configure certificate pinning
- [ ] Implement root detection
- [ ] Enable biometric authentication
- [ ] Set up crash reporting (Firebase Crashlytics)
- [ ] Configure analytics
- [ ] Test on multiple devices
- [ ] Perform security audit
- [ ] Submit to Google Play Store

---

## Best Practices

1. **Never store private keys in plain text**
2. **Always use Android Keystore for key storage**
3. **Implement certificate pinning**
4. **Use encrypted SharedPreferences**
5. **Validate all user inputs**
6. **Handle network errors gracefully**
7. **Implement proper logging (no sensitive data)**
8. **Use ProGuard/R8 for code obfuscation**
9. **Implement biometric authentication**
10. **Regular security audits**

---

**Version**: 1.0  
**Last Updated**: 2024  
**Status**: Implementation Guide
