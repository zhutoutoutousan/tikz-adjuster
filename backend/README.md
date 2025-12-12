# TikZ Diagram Editor - Backend API

FastAPI backend service with user authentication, diagram storage, and Stripe payment integration.

## Features

- **User Authentication**: JWT-based authentication with registration and login
- **Diagram Management**: CRUD operations for TikZ diagrams
- **Premium Subscriptions**: Stripe integration for monthly subscriptions
- **RESTful API**: Clean REST API with OpenAPI documentation

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Configuration

### Environment Variables

- `DATABASE_URL`: Database connection string (SQLite for dev, PostgreSQL for prod)
- `SECRET_KEY`: Secret key for JWT tokens (generate with `openssl rand -hex 32`)
- `STRIPE_SECRET_KEY`: Stripe secret key from Stripe dashboard
- `STRIPE_WEBHOOK_SECRET`: Stripe webhook secret for subscription events

### Database Setup

For development, SQLite is used by default. For production, use PostgreSQL:

```bash
# Install PostgreSQL and create database
createdb tikz_editor

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://user:password@localhost/tikz_editor
```

## Running the Server

Development:
```bash
uvicorn main:app --reload
```

Production:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication
- `POST /register` - Register new user
- `POST /token` - Login and get access token
- `GET /users/me` - Get current user info

### Diagrams
- `GET /diagrams` - List all user's diagrams
- `POST /diagrams` - Create new diagram
- `GET /diagrams/{id}` - Get specific diagram
- `PUT /diagrams/{id}` - Update diagram
- `DELETE /diagrams/{id}` - Delete diagram

### Rendering
- `POST /render` - Render TikZ code (placeholder)

### Subscriptions
- `POST /subscription/create-checkout-session` - Create Stripe checkout
- `POST /subscription/webhook` - Stripe webhook handler

## Stripe Setup

1. Create a Stripe account at https://stripe.com
2. Get your API keys from the dashboard
3. Set up webhook endpoint: `https://your-domain.com/subscription/webhook`
4. Add webhook secret to `.env`

## Security Notes

- Always use HTTPS in production
- Change `SECRET_KEY` to a strong random value
- Use environment variables for all secrets
- Enable CORS only for trusted origins

