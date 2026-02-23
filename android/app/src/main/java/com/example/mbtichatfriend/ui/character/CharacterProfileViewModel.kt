package com.example.mbtichatfriend.ui.character

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.repository.CharacterRepository
import com.example.mbtichatfriend.data.repository.FinetuneRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed class FinetuneUiState {
    object Idle : FinetuneUiState()
    object Loading : FinetuneUiState()
    data class JobStarted(val jobId: String, val trainingCount: Int) : FinetuneUiState()
    data class InProgress(val jobId: String, val status: String) : FinetuneUiState()
    data class Completed(val jobId: String, val modelId: String) : FinetuneUiState()
    data class Error(val message: String) : FinetuneUiState()
}

@HiltViewModel
class CharacterProfileViewModel @Inject constructor(
    private val characterRepo: CharacterRepository,
    private val finetuneRepo: FinetuneRepository,
    private val prefs: UserPreferences
) : ViewModel() {

    var finetuneState by mutableStateOf<FinetuneUiState>(FinetuneUiState.Idle)
        private set

    fun getCharacter(id: Long): Flow<CharacterEntity?> = characterRepo.observeById(id)

    fun deleteCharacter(id: Long, onDeleted: () -> Unit) {
        viewModelScope.launch {
            characterRepo.delete(id)
            onDeleted()
        }
    }

    fun startFinetune(character: CharacterEntity) {
        viewModelScope.launch {
            finetuneState = FinetuneUiState.Loading
            val nickname = prefs.nickname.first()
            runCatching { finetuneRepo.startFinetune(character, nickname) }
                .onSuccess { resp ->
                    finetuneState = when {
                        resp.error.isNotEmpty() -> FinetuneUiState.Error(resp.error)
                        resp.jobId.isNotEmpty() -> FinetuneUiState.JobStarted(resp.jobId, resp.trainingCount)
                        else -> FinetuneUiState.Error("알 수 없는 오류가 발생했습니다.")
                    }
                }
                .onFailure { e ->
                    finetuneState = FinetuneUiState.Error(e.message ?: "네트워크 오류")
                }
        }
    }

    fun checkFinetuneStatus(jobId: String) {
        viewModelScope.launch {
            runCatching { finetuneRepo.checkStatus(jobId) }
                .onSuccess { resp ->
                    finetuneState = when (resp.status) {
                        "succeeded" -> FinetuneUiState.Completed(resp.jobId, resp.fineTunedModel)
                        "failed", "cancelled" -> FinetuneUiState.Error("파인튜닝 실패: ${resp.error}")
                        else -> FinetuneUiState.InProgress(resp.jobId, resp.status)
                    }
                }
                .onFailure { e ->
                    finetuneState = FinetuneUiState.Error(e.message ?: "상태 조회 실패")
                }
        }
    }

    fun activateFinetunedModel(characterId: Long, modelId: String) {
        viewModelScope.launch {
            runCatching { finetuneRepo.activateModel(characterId.toString(), modelId) }
                .onSuccess {
                    // 활성화 완료 → Completed 상태 유지 (이미 succeeded)
                }
                .onFailure { e ->
                    finetuneState = FinetuneUiState.Error(e.message ?: "활성화 실패")
                }
        }
    }

    fun resetFinetuneState() {
        finetuneState = FinetuneUiState.Idle
    }
}
