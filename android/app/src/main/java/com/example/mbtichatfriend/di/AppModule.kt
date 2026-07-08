package com.example.mbtichatfriend.di

import android.content.Context
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.sqlite.db.SupportSQLiteDatabase
import com.android.billingclient.api.BillingClient
import com.example.mbtichatfriend.data.local.AppDatabase
import com.example.mbtichatfriend.data.local.CharacterDao
import com.example.mbtichatfriend.data.local.DiaryDao
import com.example.mbtichatfriend.data.local.FeedbackDao
import com.example.mbtichatfriend.data.local.MemoryDao
import com.example.mbtichatfriend.data.local.MessageDao
import com.example.mbtichatfriend.BuildConfig
import com.example.mbtichatfriend.data.remote.AuthInterceptor
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.voice.AndroidTtsEngine
import com.example.mbtichatfriend.data.voice.SpeechRecognizerManager
import com.example.mbtichatfriend.data.voice.TtsEngine
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): AppDatabase {
        return Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            "mbti_chat_db"
        )
            .addMigrations(AppDatabase.MIGRATION_1_2, AppDatabase.MIGRATION_2_3, AppDatabase.MIGRATION_3_4, AppDatabase.MIGRATION_4_5, AppDatabase.MIGRATION_5_6, AppDatabase.MIGRATION_6_7, AppDatabase.MIGRATION_7_8)
            .addCallback(object : RoomDatabase.Callback() {
                override fun onCreate(db: SupportSQLiteDatabase) {
                    super.onCreate(db)
                    // 첫 설치 시 프리셋 캐릭터 4명 시딩
                    val now = System.currentTimeMillis()
                    db.execSQL(
                        """INSERT INTO characters (name, mbti, speechStyle, relationship, affinityScore, totalMessages, avatarId, createdAt)
                           VALUES ('하루', 'ENFP', 'SWEET', 'FRIEND', 0, 0, 'BUNNY', $now)"""
                    )
                    db.execSQL(
                        """INSERT INTO characters (name, mbti, speechStyle, relationship, affinityScore, totalMessages, avatarId, createdAt)
                           VALUES ('시온', 'INTJ', 'TSUNDERE', 'FRIEND', 0, 0, 'WOLF', ${now + 1})"""
                    )
                    db.execSQL(
                        """INSERT INTO characters (name, mbti, speechStyle, relationship, affinityScore, totalMessages, avatarId, createdAt)
                           VALUES ('미루', 'INFP', 'CASUAL', 'FRIEND', 0, 0, 'UNICORN', ${now + 2})"""
                    )
                    db.execSQL(
                        """INSERT INTO characters (name, mbti, speechStyle, relationship, affinityScore, totalMessages, avatarId, createdAt)
                           VALUES ('도윤', 'ENTJ', 'CASUAL', 'SENIOR_JUNIOR', 0, 0, 'DRAGON', ${now + 3})"""
                    )
                }
            })
            .build()
    }

    @Provides
    fun provideMessageDao(db: AppDatabase): MessageDao = db.messageDao()

    @Provides
    fun provideCharacterDao(db: AppDatabase): CharacterDao = db.characterDao()

    @Provides
    fun provideDiaryDao(db: AppDatabase): DiaryDao = db.diaryDao()

    @Provides
    fun provideMemoryDao(db: AppDatabase): MemoryDao = db.memoryDao()

    @Provides
    fun provideFeedbackDao(db: AppDatabase): FeedbackDao = db.feedbackDao()

    @Provides
    @Singleton
    fun provideMoshi(): Moshi = Moshi.Builder()
        .addLast(KotlinJsonAdapterFactory())
        .build()

    @Provides
    @Singleton
    fun provideOkHttpClient(authInterceptor: AuthInterceptor): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) {
                HttpLoggingInterceptor.Level.BODY
            } else {
                HttpLoggingInterceptor.Level.NONE
            }
        }
        return OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(client: OkHttpClient, moshi: Moshi): Retrofit {
        return Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(client)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
    }

    @Provides
    @Singleton
    fun provideChatApi(retrofit: Retrofit): ChatApi {
        return retrofit.create(ChatApi::class.java)
    }

    @Provides
    @Singleton
    fun provideTtsEngine(@ApplicationContext context: Context): TtsEngine {
        return AndroidTtsEngine(context)
    }

    @Provides
    @Singleton
    fun provideSpeechRecognizerManager(@ApplicationContext context: Context): SpeechRecognizerManager {
        return SpeechRecognizerManager(context)
    }

    @Provides
    @Singleton
    fun provideBillingClient(@ApplicationContext context: Context): BillingClient {
        return BillingClient.newBuilder(context)
            .setListener { _, _ -> }
            .enablePendingPurchases()
            .build()
    }
}
