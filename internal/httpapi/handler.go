package httpapi

import (
	"context"
	"encoding/json"
	"log"
	"net/http"

	"github.com/B216-lab/backend/internal/forms"
)

type SubmissionService interface {
	Submit(ctx context.Context, in forms.SubmissionInput) (int, error)
	ValidateRespondentKey(ctx context.Context, respondentKey string) (bool, error)
}

type Handler struct {
	service      SubmissionService
	maxBodyBytes int64
}

func NewHandler(service SubmissionService, maxBodyBytes int64) *Handler {
	return &Handler{service: service, maxBodyBytes: maxBodyBytes}
}

func (h *Handler) SubmitMovementsForm(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{
			"error":   "Method Not Allowed",
			"message": "only POST is allowed",
		})
		return
	}

	r.Body = http.MaxBytesReader(w, r.Body, h.maxBodyBytes)
	defer r.Body.Close()

	var req forms.SubmissionInput
	decoder := json.NewDecoder(r.Body)
	if err := decoder.Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"error":   "Bad Request",
			"message": "invalid JSON body",
		})
		return
	}

	savedCount, err := h.service.Submit(r.Context(), req)
	if err != nil {
		if forms.IsValidationError(err) {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"error":   "Bad Request",
				"message": err.Error(),
			})
			return
		}

		writeJSON(w, http.StatusInternalServerError, map[string]any{
			"error":   "Internal Server Error",
			"message": "failed to process submission",
		})
		return
	}

	writeJSON(w, http.StatusCreated, map[string]any{
		"message":             forms.SuccessMessage,
		"savedMovementsCount": savedCount,
	})
}

func (h *Handler) ValidateRespondentKey(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{
			"error":   "Method Not Allowed",
			"message": "only GET is allowed",
		})
		return
	}

	respondentKey := r.URL.Query().Get("respondentKey")
	if respondentKey == "" {
		respondentKey = r.URL.Query().Get("key")
	}

	log.Printf("validate respondent key request: method=%s path=%s key=%q", r.Method, r.URL.Path, respondentKey)

	isValid, err := h.service.ValidateRespondentKey(r.Context(), respondentKey)
	if err != nil {
		log.Printf("validate respondent key failed: key=%q err=%v", respondentKey, err)
		if forms.IsValidationError(err) {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"error":   "Bad Request",
				"message": err.Error(),
			})
			return
		}

		writeJSON(w, http.StatusInternalServerError, map[string]any{
			"error":   "Internal Server Error",
			"message": "failed to validate respondent key",
		})
		return
	}

	if !isValid {
		log.Printf("validate respondent key not found: key=%q", respondentKey)
		writeJSON(w, http.StatusNotFound, map[string]any{
			"error":   "Not Found",
			"message": "respondent key was not found",
		})
		return
	}

	log.Printf("validate respondent key success: key=%q", respondentKey)
	w.WriteHeader(http.StatusNoContent)
}

func (h *Handler) Healthz(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
