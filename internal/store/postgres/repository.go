package postgres

import (
	"context"
	"errors"
	"fmt"

	"github.com/B216-lab/backend/internal/forms"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Repository struct {
	pool *pgxpool.Pool
}

func NewRepository(pool *pgxpool.Pool) *Repository {
	return &Repository{pool: pool}
}

func (r *Repository) Submit(ctx context.Context, in forms.Submission) (int, error) {
	tx, err := r.pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return 0, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() {
		_ = tx.Rollback(ctx)
	}()

	socialStatuses, err := loadRefIDs(ctx, tx, "social_statuses")
	if err != nil {
		return 0, err
	}
	movementTypes, err := loadRefIDs(ctx, tx, "ref_movement_type")
	if err != nil {
		return 0, err
	}
	placeTypes, err := loadRefIDs(ctx, tx, "ref_place_type")
	if err != nil {
		return 0, err
	}
	validationStatuses, err := loadRefIDs(ctx, tx, "ref_validation_status")
	if err != nil {
		return 0, err
	}
	vehicleTypes, err := loadRefIDs(ctx, tx, "ref_vehicle_type")
	if err != nil {
		return 0, err
	}

	pendingReviewID, ok := validationStatuses["PENDING_REVIEW"]
	if !ok {
		return 0, errors.New("validation status PENDING_REVIEW not found")
	}

	var socialStatusID *int64
	if in.SocialStatus != nil {
		id, exists := socialStatuses[*in.SocialStatus]
		if exists {
			socialStatusID = &id
		}
	}

	var submissionID int64
	err = tx.QueryRow(ctx, `
		INSERT INTO movements_form_submissions (
			birthday,
			gender,
			social_status_id,
			transport_cost_min,
			transport_cost_max,
			income_min,
			income_max,
			home_address,
			home_readable_address,
			movements_date
		)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
		RETURNING id
	`, in.Birthday, in.Gender, socialStatusID, in.TransportCostMin, in.TransportCostMax, in.IncomeMin, in.IncomeMax, nullableJSON(in.HomeAddress.GeoJSON), nullableString(in.HomeAddress.Readable), in.MovementsDate).Scan(&submissionID)
	if err != nil {
		return 0, fmt.Errorf("insert submission: %w", err)
	}

	savedCount := 0
	for _, movement := range in.Movements {
		movementTypeID, ok := movementTypes[movement.MovementType]
		if !ok {
			return 0, fmt.Errorf("movement type not found: %s", movement.MovementType)
		}

		departureTypeID, ok := placeTypes[movement.DepartureType]
		if !ok {
			return 0, fmt.Errorf("departure place type not found: %s", movement.DepartureType)
		}

		destinationTypeID, ok := placeTypes[movement.DestinationType]
		if !ok {
			return 0, fmt.Errorf("destination place type not found: %s", movement.DestinationType)
		}

		var vehicleTypeID *int64
		if movement.VehicleType != nil {
			id, exists := vehicleTypes[*movement.VehicleType]
			if exists {
				vehicleTypeID = &id
			}
		}

		_, err = tx.Exec(ctx, `
			INSERT INTO movements (
				movement_type_id,
				departure_time,
				destination_time,
				departure_place,
				destination_place,
				departure_place_address,
				destination_place_address,
				departure_place_type_id,
				validation_status_id,
				destination_place_type_id,
				vehicle_type_id,
				waiting_time,
				seats_amount,
				comment,
				movements_form_submission_id
			)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
		`,
			movementTypeID,
			movement.DepartureTime,
			movement.DestinationTime,
			nullableJSON(movement.DeparturePlace.GeoJSON),
			nullableJSON(movement.DestinationPlace.GeoJSON),
			nullableString(movement.DeparturePlace.Readable),
			nullableString(movement.DestinationPlace.Readable),
			departureTypeID,
			pendingReviewID,
			destinationTypeID,
			vehicleTypeID,
			movement.WaitingTime,
			movement.SeatsAmount,
			movement.Comment,
			submissionID,
		)
		if err != nil {
			return 0, fmt.Errorf("insert movement: %w", err)
		}
		savedCount++
	}

	if err = tx.Commit(ctx); err != nil {
		return 0, fmt.Errorf("commit transaction: %w", err)
	}

	return savedCount, nil
}

func loadRefIDs(ctx context.Context, tx pgx.Tx, table string) (map[string]int64, error) {
	query := fmt.Sprintf("SELECT id, code FROM %s", table)
	rows, err := tx.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("load reference table %s: %w", table, err)
	}
	defer rows.Close()

	result := make(map[string]int64)
	for rows.Next() {
		var id int64
		var code string
		if scanErr := rows.Scan(&id, &code); scanErr != nil {
			return nil, fmt.Errorf("scan reference row %s: %w", table, scanErr)
		}
		result[code] = id
	}
	if rows.Err() != nil {
		return nil, fmt.Errorf("iterate reference rows %s: %w", table, rows.Err())
	}
	return result, nil
}

func nullableString(value string) any {
	if value == "" {
		return nil
	}
	return value
}

func nullableJSON(value []byte) any {
	if len(value) == 0 {
		return nil
	}
	return value
}
