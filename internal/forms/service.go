package forms

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"
)

const SuccessMessage = "Данные формы успешно обработаны и сохранены"

type Repository interface {
	Submit(context.Context, Submission) (int, error)
}

type Service struct {
	repo  Repository
	clock func() time.Time
}

func NewService(repo Repository) *Service {
	return &Service{
		repo:  repo,
		clock: time.Now,
	}
}

type ValidationError struct {
	field string
	msg   string
}

func (e ValidationError) Error() string {
	return fmt.Sprintf("%s: %s", e.field, e.msg)
}

func IsValidationError(err error) bool {
	var ve ValidationError
	return errors.As(err, &ve)
}

func (s *Service) Submit(ctx context.Context, in SubmissionInput) (int, error) {
	normalized, err := s.normalize(in)
	if err != nil {
		return 0, err
	}
	return s.repo.Submit(ctx, normalized)
}

var movementTypes = map[string]struct{}{
	"ON_FOOT":   {},
	"TRANSPORT": {},
}

var placeTypes = map[string]struct{}{
	"HOME_RESIDENCE":                {},
	"FRIENDS_RELATIVES_HOME":        {},
	"WORKPLACE":                     {},
	"WORK_BUSINESS_TRIP":            {},
	"DAYCARE_CENTER":                {},
	"SCHOOL":                        {},
	"COLLEGE_TECHNICAL_SCHOOL":      {},
	"UNIVERSITY_INSTITUTE":          {},
	"HOSPITAL_CLINIC":               {},
	"CULTURAL_INSTITUTION":          {},
	"SPORT_FITNESS":                 {},
	"STORE_MARKET":                  {},
	"SHOPPING_ENTERTAINMENT_CENTER": {},
	"RESTAURANT_CAFE":               {},
	"SUBURB":                        {},
	"OTHER":                         {},
}

var vehicleTypes = map[string]struct{}{
	"BICYCLE":             {},
	"INDIVIDUAL_MOBILITY": {},
	"BUS":                 {},
	"SHUTTLE_TAXI":        {},
	"TRAM":                {},
	"PRIVATE_CAR":         {},
	"TROLLEYBUS":          {},
	"SUBURBAN_TRAIN":      {},
	"METRO":               {},
	"TAXI":                {},
	"CAR_SHARING":         {},
	"CITY_BIKE_RENTAL":    {},
	"SERVICE":             {},
}

var genders = map[string]struct{}{
	"MALE":   {},
	"FEMALE": {},
}

var socialStatuses = map[string]struct{}{
	"WORKING":                  {},
	"STUDENT":                  {},
	"UNIVERSITY_STUDENT":       {},
	"PENSIONER":                {},
	"PERSON_WITH_DISABILITIES": {},
	"UNEMPLOYED":               {},
	"HOUSEWIFE":                {},
	"TEMPORARILY_UNEMPLOYED":   {},
}

func (s *Service) normalize(in SubmissionInput) (Submission, error) {
	movementDate, err := s.parseDateOrToday(in.MovementsDate)
	if err != nil {
		return Submission{}, ValidationError{field: "movementsDate", msg: "must be YYYY-MM-DD"}
	}

	sub := Submission{
		TransportCostMin: in.TransportCostMin,
		TransportCostMax: in.TransportCostMax,
		IncomeMin:        in.IncomeMin,
		IncomeMax:        in.IncomeMax,
		MovementsDate:    movementDate,
		Movements:        make([]Movement, 0, len(in.Movements)),
	}

	if birthday := strings.TrimSpace(in.Birthday); birthday != "" {
		parsedBirthday, parseErr := time.Parse("2006-01-02", birthday)
		if parseErr == nil {
			sub.Birthday = &parsedBirthday
		}
	}

	if normalizedGender := strings.ToUpper(strings.TrimSpace(in.Gender)); normalizedGender != "" {
		if _, ok := genders[normalizedGender]; ok {
			sub.Gender = &normalizedGender
		}
	}

	if normalizedStatus := strings.ToUpper(strings.TrimSpace(in.SocialStatus)); normalizedStatus != "" {
		if _, ok := socialStatuses[normalizedStatus]; ok {
			sub.SocialStatus = &normalizedStatus
		}
	}

	sub.HomeAddress = normalizeAddress(in.HomeAddress)

	for i, movementIn := range in.Movements {
		movement, normalizeErr := normalizeMovement(movementIn, movementDate, i)
		if normalizeErr != nil {
			return Submission{}, normalizeErr
		}
		sub.Movements = append(sub.Movements, movement)
	}

	return sub, nil
}

func normalizeMovement(in MovementInput, movementDate time.Time, idx int) (Movement, error) {
	movementType := strings.ToUpper(strings.TrimSpace(in.MovementType))
	if movementType == "" {
		return Movement{}, ValidationError{field: fmt.Sprintf("movements[%d].movementType", idx), msg: "is required"}
	}
	if _, ok := movementTypes[movementType]; !ok {
		return Movement{}, ValidationError{field: fmt.Sprintf("movements[%d].movementType", idx), msg: "unsupported value"}
	}

	departurePlace := strings.ToUpper(strings.TrimSpace(in.DeparturePlace))
	if departurePlace == "" {
		return Movement{}, ValidationError{field: fmt.Sprintf("movements[%d].departurePlace", idx), msg: "is required"}
	}
	if _, ok := placeTypes[departurePlace]; !ok {
		return Movement{}, ValidationError{field: fmt.Sprintf("movements[%d].departurePlace", idx), msg: "unsupported value"}
	}

	arrivalPlace := strings.ToUpper(strings.TrimSpace(in.ArrivalPlace))
	if arrivalPlace == "" {
		return Movement{}, ValidationError{field: fmt.Sprintf("movements[%d].arrivalPlace", idx), msg: "is required"}
	}
	if _, ok := placeTypes[arrivalPlace]; !ok {
		return Movement{}, ValidationError{field: fmt.Sprintf("movements[%d].arrivalPlace", idx), msg: "unsupported value"}
	}

	departureTime, err := parseOptionalTime(in.DepartureTime, movementDate)
	if err != nil {
		return Movement{}, ValidationError{field: fmt.Sprintf("movements[%d].departureTime", idx), msg: "must be HH:mm"}
	}

	arrivalTime, err := parseOptionalTime(in.ArrivalTime, movementDate)
	if err != nil {
		return Movement{}, ValidationError{field: fmt.Sprintf("movements[%d].arrivalTime", idx), msg: "must be HH:mm"}
	}

	movement := Movement{
		MovementType:     movementType,
		DepartureType:    departurePlace,
		DestinationType:  arrivalPlace,
		DepartureTime:    departureTime,
		DestinationTime:  arrivalTime,
		DeparturePlace:   normalizeAddress(in.DepartureAddress),
		DestinationPlace: normalizeAddress(in.ArrivalAddress),
		SeatsAmount:      in.NumberPeopleInCar,
	}

	if in.WaitAtStartMinutes != nil {
		movement.WaitingTime = in.WaitAtStartMinutes
	} else if value := strings.TrimSpace(in.WaitBetweenTransfersMinutes); value != "" {
		parsedWaiting, parseErr := strconv.Atoi(value)
		if parseErr == nil {
			movement.WaitingTime = &parsedWaiting
		}
	}

	if len(in.Transport) > 0 {
		candidate := strings.ToUpper(strings.TrimSpace(in.Transport[0]))
		if _, ok := vehicleTypes[candidate]; ok {
			movement.VehicleType = &candidate
		}
	}

	if comment := strings.TrimSpace(in.Comment); comment != "" {
		movement.Comment = &comment
	}

	return movement, nil
}

func (s *Service) parseDateOrToday(raw string) (time.Time, error) {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		now := s.clock().UTC()
		return time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC), nil
	}
	return time.Parse("2006-01-02", trimmed)
}

func parseOptionalTime(raw string, movementDate time.Time) (*time.Time, error) {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		return nil, nil
	}

	parsed, err := time.Parse("15:04", trimmed)
	if err != nil {
		return nil, err
	}

	timestamp := time.Date(
		movementDate.Year(),
		movementDate.Month(),
		movementDate.Day(),
		parsed.Hour(),
		parsed.Minute(),
		0,
		0,
		time.UTC,
	)

	return &timestamp, nil
}

func normalizeAddress(in AddressInput) Address {
	address := Address{Readable: strings.TrimSpace(in.Value)}

	if raw := firstNonEmptyGeoJSON(in); len(raw) > 0 && isValidGeoJSONPoint(raw) {
		address.GeoJSON = compactJSON(raw)
		return address
	}

	if in.Latitude != nil && in.Longitude != nil {
		geo := map[string]any{
			"type":        "Point",
			"coordinates": []float64{*in.Longitude, *in.Latitude},
		}
		serialized, err := json.Marshal(geo)
		if err == nil {
			address.GeoJSON = serialized
		}
	}

	return address
}

func firstNonEmptyGeoJSON(in AddressInput) []byte {
	if len(bytes.TrimSpace(in.GeoJSON)) > 0 {
		return in.GeoJSON
	}
	if len(bytes.TrimSpace(in.GeoJSONV2)) > 0 {
		return in.GeoJSONV2
	}
	return nil
}

func isValidGeoJSONPoint(raw []byte) bool {
	var obj struct {
		Type        string    `json:"type"`
		Coordinates []float64 `json:"coordinates"`
	}

	if err := json.Unmarshal(raw, &obj); err != nil {
		return false
	}

	if obj.Type != "Point" {
		return false
	}

	return len(obj.Coordinates) == 2
}

func compactJSON(raw []byte) []byte {
	var v any
	if err := json.Unmarshal(raw, &v); err != nil {
		return nil
	}

	compacted, err := json.Marshal(v)
	if err != nil {
		return nil
	}
	return compacted
}
