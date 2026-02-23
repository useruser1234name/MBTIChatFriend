package com.example.mbtichatfriend.data.remote

import android.content.Context
import android.util.Log
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import com.google.android.libraries.identity.googleid.GetGoogleIdOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.google.firebase.FirebaseApp
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.FirebaseUser
import com.google.firebase.auth.GoogleAuthProvider
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await
import javax.inject.Inject
import javax.inject.Singleton

sealed class AuthState {
    data object Loading : AuthState()
    data object NotAuthenticated : AuthState()
    data class Authenticated(val user: FirebaseUser) : AuthState()
    data object FirebaseUnavailable : AuthState()
}

@Singleton
class FirebaseAuthManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val auth: FirebaseAuth? = try {
        FirebaseApp.initializeApp(context)
        FirebaseAuth.getInstance()
    } catch (e: Exception) {
        Log.w(TAG, "Firebase not available: ${e.message}")
        null
    }

    val isFirebaseAvailable: Boolean get() = auth != null

    val currentUser: FirebaseUser? get() = auth?.currentUser

    val authStateFlow: Flow<AuthState> = callbackFlow {
        if (auth == null) {
            trySend(AuthState.FirebaseUnavailable)
            awaitClose()
            return@callbackFlow
        }

        val listener = FirebaseAuth.AuthStateListener { firebaseAuth ->
            val user = firebaseAuth.currentUser
            val state = if (user != null) {
                AuthState.Authenticated(user)
            } else {
                AuthState.NotAuthenticated
            }
            trySend(state)
        }
        auth.addAuthStateListener(listener)
        awaitClose { auth.removeAuthStateListener(listener) }
    }

    suspend fun signInAnonymously(): Result<FirebaseUser> {
        val firebaseAuth = auth ?: return Result.failure(
            IllegalStateException("Firebase not available")
        )
        return try {
            val result = firebaseAuth.signInAnonymously().await()
            val user = result.user ?: throw IllegalStateException("User is null after sign-in")
            Result.success(user)
        } catch (e: Exception) {
            Log.e(TAG, "Anonymous sign-in failed", e)
            Result.failure(e)
        }
    }

    suspend fun signInWithGoogle(activityContext: Context): Result<FirebaseUser> {
        val firebaseAuth = auth ?: return Result.failure(
            IllegalStateException("Firebase not available")
        )
        return try {
            val credentialManager = CredentialManager.create(activityContext)

            val googleIdOption = GetGoogleIdOption.Builder()
                .setFilterByAuthorizedAccounts(false)
                .setServerClientId(getWebClientId())
                .build()

            val request = GetCredentialRequest.Builder()
                .addCredentialOption(googleIdOption)
                .build()

            val result = credentialManager.getCredential(activityContext, request)
            val credential = result.credential

            if (credential is CustomCredential &&
                credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL
            ) {
                val googleIdTokenCredential = GoogleIdTokenCredential.createFrom(credential.data)
                val firebaseCredential = GoogleAuthProvider.getCredential(
                    googleIdTokenCredential.idToken, null
                )

                // 익명 계정이면 링크, 아니면 새로 로그인
                val currentUser = firebaseAuth.currentUser
                val authResult = if (currentUser != null && currentUser.isAnonymous) {
                    currentUser.linkWithCredential(firebaseCredential).await()
                } else {
                    firebaseAuth.signInWithCredential(firebaseCredential).await()
                }

                val user = authResult.user
                    ?: throw IllegalStateException("User is null after Google sign-in")
                Result.success(user)
            } else {
                Result.failure(IllegalStateException("Unexpected credential type"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Google sign-in failed", e)
            Result.failure(e)
        }
    }

    suspend fun getIdToken(): String? {
        return try {
            auth?.currentUser?.getIdToken(false)?.await()?.token
        } catch (e: Exception) {
            Log.w(TAG, "Failed to get ID token", e)
            null
        }
    }

    fun signOut() {
        auth?.signOut()
    }

    private fun getWebClientId(): String {
        // google-services.json의 oauth_client에서 web client ID를 가져옴
        // 실제 프로젝트에서는 BuildConfig 또는 string resource에서 읽음
        val resId = context.resources.getIdentifier(
            "default_web_client_id", "string", context.packageName
        )
        return if (resId != 0) context.getString(resId) else ""
    }

    companion object {
        private const val TAG = "FirebaseAuthManager"
    }
}
