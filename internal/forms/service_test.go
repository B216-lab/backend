package forms

import (
	"context"
	"testing"
	"time"
)

type fakeRepo struct {
	captured     Submission
	count        int
	allowedKeys  map[string]bool
	validatedKey string
}

func (r *fakeRepo) Submit(_ context.Context, in Submission) (int, error) {
	r.captured = in
	return r.count, nil
}

func (r *fakeRepo) IsRespondentKeyAllowed(_ context.Context, respondentKey string) (bool, error) {
	r.validatedKey = respondentKey
	return r.allowedKeys[respondentKey], nil
}

func TestSubmit_ShouldNormalizeAndPersist_WhenInputIsValid(t *testing.T) {
	repo := &fakeRepo{count: 1}
	service := NewService(repo)
	service.clock = func() time.Time { return time.Date(2026, 4, 1, 10, 0, 0, 0, time.UTC) }

	count, err := service.Submit(context.Background(), SubmissionInput{
		MovementsDate: "2026-04-01",
		Movements: []MovementInput{{
			MovementType:   "ON_FOOT",
			DeparturePlace: "HOME_RESIDENCE",
			ArrivalPlace:   "SCHOOL",
			DepartureTime:  "08:30",
			ArrivalTime:    "09:00",
		}},
	})
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if count != 1 {
		t.Fatalf("expected count 1, got %d", count)
	}
	if len(repo.captured.Movements) != 1 {
		t.Fatalf("expected one movement, got %d", len(repo.captured.Movements))
	}
	if repo.captured.Movements[0].DepartureTime == nil {
		t.Fatal("expected departure time to be set")
	}
}

func TestSubmit_ShouldReturnValidationError_WhenMovementTypeInvalid(t *testing.T) {
	repo := &fakeRepo{}
	service := NewService(repo)

	_, err := service.Submit(context.Background(), SubmissionInput{
		MovementsDate: "2026-04-01",
		Movements: []MovementInput{{
			MovementType:   "BAD",
			DeparturePlace: "HOME_RESIDENCE",
			ArrivalPlace:   "SCHOOL",
		}},
	})

	if err == nil {
		t.Fatal("expected validation error")
	}
	if !IsValidationError(err) {
		t.Fatalf("expected validation error type, got %T", err)
	}
}

func TestSubmit_ShouldBuildGeoJSONFromCoordinates_WhenGeoJSONAbsent(t *testing.T) {
	repo := &fakeRepo{count: 1}
	service := NewService(repo)
	lat := 55.7558
	lon := 37.6173

	_, err := service.Submit(context.Background(), SubmissionInput{
		MovementsDate: "2026-04-01",
		Movements: []MovementInput{{
			MovementType:   "ON_FOOT",
			DeparturePlace: "HOME_RESIDENCE",
			ArrivalPlace:   "SCHOOL",
			DepartureAddress: AddressInput{
				Value:     "Moscow",
				Latitude:  &lat,
				Longitude: &lon,
			},
		}},
	})
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	geo := string(repo.captured.Movements[0].DeparturePlace.GeoJSON)
	expected := `{"coordinates":[37.6173,55.7558],"type":"Point"}`
	if geo != expected {
		t.Fatalf("unexpected geojson, got %s", geo)
	}
}

func TestSubmit_ShouldAllowAnonymousSubmission_WhenRespondentKeyMissing(t *testing.T) {
	repo := &fakeRepo{count: 1}
	service := NewService(repo)

	_, err := service.Submit(context.Background(), SubmissionInput{
		MovementsDate: "2026-04-01",
		Movements: []MovementInput{{
			MovementType:   "ON_FOOT",
			DeparturePlace: "HOME_RESIDENCE",
			ArrivalPlace:   "SCHOOL",
		}},
	})
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if repo.validatedKey != "" {
		t.Fatalf("expected respondent key validation to be skipped, got %q", repo.validatedKey)
	}
}

func TestSubmit_ShouldRejectInvalidRespondentKey_WhenProvided(t *testing.T) {
	repo := &fakeRepo{
		allowedKeys: map[string]bool{},
	}
	service := NewService(repo)

	_, err := service.Submit(context.Background(), SubmissionInput{
		RespondentKey: "bad-key",
		MovementsDate: "2026-04-01",
		Movements: []MovementInput{{
			MovementType:   "ON_FOOT",
			DeparturePlace: "HOME_RESIDENCE",
			ArrivalPlace:   "SCHOOL",
		}},
	})

	if err == nil {
		t.Fatal("expected validation error")
	}
	if !IsValidationError(err) {
		t.Fatalf("expected validation error type, got %T", err)
	}
	if repo.validatedKey != "bad-key" {
		t.Fatalf("expected validated key to be captured, got %q", repo.validatedKey)
	}
}

func TestValidateRespondentKey_ShouldReturnTrue_WhenKeyAllowed(t *testing.T) {
	repo := &fakeRepo{
		allowedKeys: map[string]bool{"good-key": true},
	}
	service := NewService(repo)

	isValid, err := service.ValidateRespondentKey(context.Background(), "good-key")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if !isValid {
		t.Fatal("expected key to be valid")
	}
}

func TestValidateRespondentKey_ShouldRequireNonEmptyKey(t *testing.T) {
	service := NewService(&fakeRepo{})

	_, err := service.ValidateRespondentKey(context.Background(), "   ")
	if err == nil {
		t.Fatal("expected validation error")
	}
	if !IsValidationError(err) {
		t.Fatalf("expected validation error type, got %T", err)
	}
}
