package forms

import (
	"encoding/json"
	"time"
)

type FlexibleString string

func (s *FlexibleString) UnmarshalJSON(data []byte) error {
	if string(data) == "null" {
		*s = ""
		return nil
	}

	var text string
	if err := json.Unmarshal(data, &text); err == nil {
		*s = FlexibleString(text)
		return nil
	}

	var number json.Number
	if err := json.Unmarshal(data, &number); err != nil {
		return err
	}
	*s = FlexibleString(number.String())
	return nil
}

func (s FlexibleString) String() string {
	return string(s)
}

type AddressInput struct {
	Value     string          `json:"value"`
	GeoJSON   json.RawMessage `json:"geojson"`
	GeoJSONV2 json.RawMessage `json:"geo_json"`
	Latitude  *float64        `json:"latitude"`
	Longitude *float64        `json:"longitude"`
	Data      *AddressData    `json:"data"`
}

type AddressData struct {
	GeoLat FlexibleString `json:"geo_lat"`
	GeoLon FlexibleString `json:"geo_lon"`
}

type MovementInput struct {
	MovementType                string         `json:"movementType"`
	Transport                   []string       `json:"transport"`
	NumberPeopleInCar           *int           `json:"numberPeopleInCar"`
	WalkToStartMinutes          *int           `json:"walkToStartMinutes"`
	WaitAtStartMinutes          *int           `json:"waitAtStartMinutes"`
	NumberOfTransfers           *int           `json:"numberOfTransfers"`
	WaitBetweenTransfersMinutes FlexibleString `json:"waitBetweenTransfersMinutes"`
	DepartureTime               string         `json:"departureTime"`
	DeparturePlace              string         `json:"departurePlace"`
	DepartureAddress            AddressInput   `json:"departureAddress"`
	ArrivalTime                 string         `json:"arrivalTime"`
	ArrivalPlace                string         `json:"arrivalPlace"`
	WalkFromFinishMinutes       *int           `json:"walkFromFinishMinutes"`
	TripCost                    FlexibleString `json:"tripCost"`
	ArrivalAddress              AddressInput   `json:"arrivalAddress"`
	Comment                     string         `json:"comment"`
}

type SubmissionInput struct {
	RespondentKey    string          `json:"respondentKey"`
	Birthday         string          `json:"birthday"`
	Gender           string          `json:"gender"`
	SocialStatus     string          `json:"socialStatus"`
	TransportCostMin *int            `json:"transportCostMin"`
	TransportCostMax *int            `json:"transportCostMax"`
	HomeAddress      AddressInput    `json:"homeAddress"`
	IncomeMin        *int            `json:"incomeMin"`
	IncomeMax        *int            `json:"incomeMax"`
	MovementsDate    string          `json:"movementsDate"`
	Movements        []MovementInput `json:"movements"`
}

type Address struct {
	Readable string
	GeoJSON  []byte
}

type Movement struct {
	MovementType     string
	DepartureTime    *time.Time
	DestinationTime  *time.Time
	DeparturePlace   Address
	DestinationPlace Address
	DepartureType    string
	DestinationType  string
	VehicleType      *string
	WaitingTime      *int
	SeatsAmount      *int
	Comment          *string
}

type Submission struct {
	RespondentKey    *string
	Birthday         *time.Time
	Gender           *string
	SocialStatus     *string
	TransportCostMin *int
	TransportCostMax *int
	HomeAddress      Address
	IncomeMin        *int
	IncomeMax        *int
	MovementsDate    time.Time
	Movements        []Movement
}
