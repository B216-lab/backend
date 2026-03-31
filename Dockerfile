FROM golang:1.26-alpine AS builder
WORKDIR /src

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /out/backend ./cmd/api

FROM alpine:3.22
RUN addgroup -S app && adduser -S app -G app \
    && apk add --no-cache ca-certificates tzdata

WORKDIR /app
COPY --from=builder /out/backend /app/backend

ENV SERVER_PORT=8081
EXPOSE 8081
USER app

ENTRYPOINT ["/app/backend"]
