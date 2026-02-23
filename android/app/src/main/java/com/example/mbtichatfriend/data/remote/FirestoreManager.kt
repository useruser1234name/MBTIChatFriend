package com.example.mbtichatfriend.data.remote

import android.util.Log
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import kotlinx.coroutines.tasks.await
import javax.inject.Inject
import javax.inject.Singleton

data class UserProfile(
    val nickname: String = "",
    val gender: String = "",
    val ageGroup: String = "",
    val userMbti: String = "",
    val partnerMbti: String = "",
    val speechStyle: String = "",
    val relationship: String = "",
    val updatedAt: Long = System.currentTimeMillis()
)

@Singleton
class FirestoreManager @Inject constructor() {

    private val firestore: FirebaseFirestore? = try {
        FirebaseFirestore.getInstance()
    } catch (e: Exception) {
        Log.w(TAG, "Firestore not available: ${e.message}")
        null
    }

    val isAvailable: Boolean get() = firestore != null

    suspend fun saveProfile(uid: String, profile: UserProfile): Boolean {
        val db = firestore ?: return false
        return try {
            val data = mapOf(
                "nickname" to profile.nickname,
                "gender" to profile.gender,
                "ageGroup" to profile.ageGroup,
                "userMbti" to profile.userMbti,
                "partnerMbti" to profile.partnerMbti,
                "speechStyle" to profile.speechStyle,
                "relationship" to profile.relationship,
                "updatedAt" to profile.updatedAt
            )
            db.collection(COLLECTION_USERS).document(uid)
                .set(data, SetOptions.merge())
                .await()
            Log.d(TAG, "Profile saved for uid=$uid")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to save profile", e)
            false
        }
    }

    suspend fun getProfile(uid: String): UserProfile? {
        val db = firestore ?: return null
        return try {
            val snapshot = db.collection(COLLECTION_USERS).document(uid)
                .get()
                .await()
            if (snapshot.exists()) {
                UserProfile(
                    nickname = snapshot.getString("nickname") ?: "",
                    gender = snapshot.getString("gender") ?: "",
                    ageGroup = snapshot.getString("ageGroup") ?: "",
                    userMbti = snapshot.getString("userMbti") ?: "",
                    partnerMbti = snapshot.getString("partnerMbti") ?: "",
                    speechStyle = snapshot.getString("speechStyle") ?: "",
                    relationship = snapshot.getString("relationship") ?: "",
                    updatedAt = snapshot.getLong("updatedAt") ?: 0L
                )
            } else {
                null
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get profile", e)
            null
        }
    }

    suspend fun deleteProfile(uid: String): Boolean {
        val db = firestore ?: return false
        return try {
            db.collection(COLLECTION_USERS).document(uid)
                .delete()
                .await()
            Log.d(TAG, "Profile deleted for uid=$uid")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to delete profile", e)
            false
        }
    }

    companion object {
        private const val TAG = "FirestoreManager"
        private const val COLLECTION_USERS = "users"
    }
}
