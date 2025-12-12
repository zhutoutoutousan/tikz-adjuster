"""
TikZ Diagram Editor - Backend API
FastAPI backend with authentication, payment, and TikZ rendering
"""

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import stripe
import os
from dotenv import load_dotenv

from database import SessionLocal, engine, Base
from models import User, Diagram
from schemas import UserCreate, UserResponse, DiagramCreate, DiagramResponse, Token

load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="TikZ Diagram Editor API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

# Create database tables
Base.metadata.create_all(bind=engine)


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Authentication helpers
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


# Routes
@app.get("/")
async def root():
    return {"message": "TikZ Diagram Editor API"}


@app.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if user exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        is_premium=False
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login and get access token"""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@app.post("/diagrams", response_model=DiagramResponse)
async def create_diagram(
    diagram: DiagramCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new diagram"""
    db_diagram = Diagram(
        title=diagram.title,
        tikz_code=diagram.tikz_code,
        user_id=current_user.id
    )
    db.add(db_diagram)
    db.commit()
    db.refresh(db_diagram)
    return db_diagram


@app.get("/diagrams", response_model=List[DiagramResponse])
async def get_diagrams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all diagrams for current user"""
    diagrams = db.query(Diagram).filter(Diagram.user_id == current_user.id).all()
    return diagrams


@app.get("/diagrams/{diagram_id}", response_model=DiagramResponse)
async def get_diagram(
    diagram_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific diagram"""
    diagram = db.query(Diagram).filter(
        Diagram.id == diagram_id,
        Diagram.user_id == current_user.id
    ).first()
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")
    return diagram


@app.put("/diagrams/{diagram_id}", response_model=DiagramResponse)
async def update_diagram(
    diagram_id: int,
    diagram: DiagramCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a diagram"""
    db_diagram = db.query(Diagram).filter(
        Diagram.id == diagram_id,
        Diagram.user_id == current_user.id
    ).first()
    if not db_diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")
    
    db_diagram.title = diagram.title
    db_diagram.tikz_code = diagram.tikz_code
    db_diagram.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_diagram)
    return db_diagram


@app.delete("/diagrams/{diagram_id}")
async def delete_diagram(
    diagram_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a diagram"""
    diagram = db.query(Diagram).filter(
        Diagram.id == diagram_id,
        Diagram.user_id == current_user.id
    ).first()
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")
    
    db.delete(diagram)
    db.commit()
    return {"message": "Diagram deleted successfully"}


@app.post("/render")
async def render_tikz(tikz_code: str, current_user: User = Depends(get_current_user)):
    """Render TikZ code to image (SVG/PNG)"""
    # This is a placeholder - in production, you'd use a LaTeX rendering service
    # Options: LaTeX compilation, TikZ.js, or external service
    try:
        # For now, return the code as-is
        # In production, compile LaTeX and return image
        return {
            "status": "success",
            "message": "Rendering not yet implemented - use client-side rendering",
            "code": tikz_code
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/subscription/create-checkout-session")
async def create_checkout_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create Stripe checkout session for premium subscription"""
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=current_user.email,
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'TikZ Editor Premium',
                    },
                    'unit_amount': 999,  # $9.99
                    'recurring': {
                        'interval': 'month',
                    },
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url='http://localhost:3000/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='http://localhost:3000/cancel',
            metadata={
                'user_id': str(current_user.id),
            }
        )
        return {"checkout_url": checkout_session.url, "session_id": checkout_session.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/subscription/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET", "")
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session['metadata']['user_id']
        # Update user to premium
        db = SessionLocal()
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user:
            user.is_premium = True
            db.commit()
        db.close()
    
    return {"status": "success"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

