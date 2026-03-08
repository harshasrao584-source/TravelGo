

```bash
export AWS_DEFAULT_REGION=us-east-1
export SNS_TOPIC_ARN=arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:booking-confirmation-seat
export SECRET_KEY=your-random-secret-key-here
export FLASK_DEBUG=false
```


```bash
# Development (port 5000)
python3 app.py

# Production (port 80)
sudo python3 app.py
```

## 4. DynamoDB Tables Required
- **Users**    — Partition key: email (String)
- **Bookings** — Partition key: booking_id (String)
- **Seats**    — Partition key: seat_id (String)

## 5. Project Structure
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
```
