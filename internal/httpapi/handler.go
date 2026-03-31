package httpapi

import (
	"context"
	"encoding/json"
	"net/http"

	"github.com/B216-lab/backend/internal/forms"
)

type SubmissionService interface {
	Submit(ctx context.Context, in forms.SubmissionInput) (int, error)
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

func (h *Handler) Healthz(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
