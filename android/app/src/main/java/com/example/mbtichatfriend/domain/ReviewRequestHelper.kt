package com.example.mbtichatfriend.domain

import android.app.Activity
import com.google.android.play.core.review.ReviewManagerFactory

// ── 35차 스프린트: Play 인앱 리뷰 요청 헬퍼 ─────────────────────────────────
// 조건: 품질 세션(qualitySessionCount) 3회 이상 달성 시 인앱 리뷰 다이얼로그 표시

object ReviewRequestHelper {
    fun requestReviewIfEligible(activity: Activity, qualitySessionCount: Int) {
        if (qualitySessionCount >= 3) {
            val manager = ReviewManagerFactory.create(activity)
            val request = manager.requestReviewFlow()
            request.addOnCompleteListener { task ->
                if (task.isSuccessful) {
                    manager.launchReviewFlow(activity, task.result)
                }
            }
        }
    }
}
