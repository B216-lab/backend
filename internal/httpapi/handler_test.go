package httpapi

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/B216-lab/backend/internal/forms"
)

type fakeSubmissionService struct {
	validateResult bool
	validateErr    error
	validateKey    string
}

func (s *fakeSubmissionService) Submit(_ context.Context, _ forms.SubmissionInput) (int, error) {
	return 0, nil
}

func (s *fakeSubmissionService) ValidateRespondentKey(_ context.Context, respondentKey string) (bool, error) {
	s.validateKey = respondentKey
	return s.validateResult, s.validateErr
}

func TestValidateRespondentKey_ReturnsNoContent_WhenKeyIsAllowed(t *testing.T) {
	handler := NewHandler(&fakeSubmissionService{validateResult: true}, 1024)
	req := httptest.NewRequest(http.MethodGet, "/v1/public/forms/movements/respondent-keys/validate?respondentKey=abc-123", nil)
	rec := httptest.NewRecorder()

	handler.ValidateRespondentKey(rec, req)

	if rec.Code != http.StatusNoContent {
		t.Fatalf("expected status %d, got %d", http.StatusNoContent, rec.Code)
	}
}

func TestValidateRespondentKey_ReturnsNotFound_WhenKeyIsUnknown(t *testing.T) {
	handler := NewHandler(&fakeSubmissionService{validateResult: false}, 1024)
	req := httptest.NewRequest(http.MethodGet, "/v1/public/forms/movements/respondent-keys/validate?respondentKey=missing", nil)
	rec := httptest.NewRecorder()

	handler.ValidateRespondentKey(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("expected status %d, got %d", http.StatusNotFound, rec.Code)
	}
}

func TestValidateRespondentKey_ReturnsBadRequest_WhenKeyIsMissing(t *testing.T) {
	handler := NewHandler(&fakeSubmissionService{
		validateErr: forms.ValidationError{},
	}, 1024)
	req := httptest.NewRequest(http.MethodGet, "/v1/public/forms/movements/respondent-keys/validate", nil)
	rec := httptest.NewRecorder()

	handler.ValidateRespondentKey(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected status %d, got %d", http.StatusBadRequest, rec.Code)
	}
}
