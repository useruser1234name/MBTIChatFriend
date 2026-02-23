package com.example.mbtichatfriend.data.repository

import android.content.Context
import android.util.Log
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.AuthState
import com.example.mbtichatfriend.data.remote.FirebaseAuthManager
import com.example.mbtichatfriend.data.remote.FirestoreManager
import com.example.mbtichatfriend.data.remote.UserProfile
import com.google.firebase.auth.FirebaseUser
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val authManager: FirebaseAuthManager,
    private val firestoreManager: FirestoreManager,
    private val prefs: UserPreferences,
    @ApplicationContext private val context: Context
) {
    val authStateFlow: Flow<AuthState> = authManager.authStateFlow
    val isFirebaseAvailable: Boolean get() = authManager.isFirebaseAvailable
    val authProvider: Flow<String> = prefs.authProvider

    suspend fun signInAnonymously(): Result<FirebaseUser> {
        val result = authManager.signInAnonymously()
        result.onSuccess { user ->
            prefs.updateFirebaseUid(user.uid)
            prefs.updateAuthProvider("anonymous")
            syncProfileToFirestore(user.uid)
        }
        return result
    }

    suspend fun signInWithGoogle(activityContext: Context): Result<FirebaseUser> {
        val result = authManager.signInWithGoogle(activityContext)
        result.onSuccess { user ->
            prefs.updateFirebaseUid(user.uid)
            prefs.updateAuthProvider("google")
            // Google 계정의 이름으로 닉네임 업데이트
            user.displayName?.takeIf { it.isNotBlank() }?.let { name ->
                val trimmed = if (name.length > 8) name.substring(0, 8) else name
                prefs.updateNickname(trimmed)
            }
            // Firestore에서 기존 프로필 복원 시도, 없으면 현재 프로필 업로드
            val restored = restoreProfileFromFirestore(user.uid)
            if (!restored) {
                syncProfileToFirestore(user.uid)
            }
        }
        return result
    }

    suspend fun linkGoogleAccount(activityContext: Context): Result<FirebaseUser> {
        return signInWithGoogle(activityContext)
    }

    suspend fun getIdToken(): String? = authManager.getIdToken()

    suspend fun signOut() {
        authManager.signOut()
        prefs.updateFirebaseUid("")
        prefs.updateAuthProvider("none")
    }

    fun skipAuth() {
        // Firebase 없이 로컬 모드로 사용
    }

    suspend fun syncProfileToFirestore(uid: String? = null) {
        val targetUid = uid ?: prefs.firebaseUid.first()
        if (targetUid.isBlank()) return
        try {
            val profile = UserProfile(
                nickname = prefs.nickname.first(),
                gender = prefs.gender.first(),
                ageGroup = prefs.ageGroup.first(),
                userMbti = prefs.userMbti.first(),
                partnerMbti = prefs.partnerMbti.first(),
                speechStyle = prefs.speechStyle.first(),
                relationship = prefs.relationship.first()
            )
            firestoreManager.saveProfile(targetUid, profile)
        } catch (e: Exception) {
            Log.w(TAG, "Failed to sync profile to Firestore", e)
        }
    }

    private suspend fun restoreProfileFromFirestore(uid: String): Boolean {
        return try {
            val profile = firestoreManager.getProfile(uid) ?: return false
            if (profile.nickname.isBlank()) return false
            prefs.saveOnboardingData(
                nickname = profile.nickname,
                gender = profile.gender,
                ageGroup = profile.ageGroup,
                partnerMbti = profile.partnerMbti,
                speechStyle = profile.speechStyle,
                relationship = profile.relationship,
                userMbti = profile.userMbti
            )
            Log.d(TAG, "Profile restored from Firestore for uid=$uid")
            true
        } catch (e: Exception) {
            Log.w(TAG, "Failed to restore profile from Firestore", e)
            false
        }
    }

    companion object {
        private const val TAG = "AuthRepository"
    }
}
