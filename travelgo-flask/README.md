# TravelGo Flask Application

## 🚀 Demo
🌐 **Live Demo**: [https://travelgo-demo.example.com](https://travelgo-demo.example.com)

*Note: Demo link will be active once deployed to AWS EC2*

---

## 1. Overview
TravelGo is a cloud-powered real-time booking platform built with Flask and AWS services.

## 2. Features
- User registration and authentication
- Browse travel destinations
- Real-time seat selection
- Booking management
- AWS DynamoDB integration
- AWS SNS notifications

## 3. Environment Variables
```bash
export AWS_DEFAULT_REGION=us-east-1
export SNS_TOPIC_ARN=arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:booking-confirmation-seat
export SECRET_KEY=your-random-secret-key-here
export FLASK_DEBUG=false
```

## 4. Running the App
```bash
# Development (port 5000)
python3 app.py

# Production (port 80)
sudo python3 app.py
```

## 5. DynamoDB Tables Required
- **Users**    — Partition key: email (String)
- **Bookings** — Partition key: booking_id (String)
- **Seats**    — Partition key: seat_id (String)

## 6. Project Structure
```
travelgo/
├── app.py                  ← Main Flask app
├── requirements.txt
└── templates/
    ├── base.html           ← Layout, nav, styles
    ├── index.html          ← Home / destinations
    ├── register.html       ← User registration
    ├── login.html          ← Login form
    ├── destination.html    ← Seat selection + booking
    ├── dashboard.html      ← User's bookings
    ├── booking_detail.html ← Confirmation page
    └── error.html          ← 404 / 500 errors
