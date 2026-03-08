"""
TravelGo — A Cloud-Powered Real-Time Booking Platform
Flask Application Entry Point
"""

import os
import uuid
import boto3
import hashlib
import hmac
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from botocore.exceptions import ClientError

# ─────────────────────────────────────────────
# APP CONFIG
# ─────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "travelgo-secret-2024-change-in-prod")

# AWS Config — set via environment variables on EC2
AWS_REGION      = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
SNS_TOPIC_ARN   = os.environ.get("SNS_TOPIC_ARN", "")   # Set after creating SNS topic

# Use mock DB for demo (set to False to use real AWS)
USE_MOCK_DB = os.environ.get("USE_MOCK_DB", "true").lower() == "true"

# ─────────────────────────────────────────────
# AWS CLIENTS
# ─────────────────────────────────────────────
if not USE_MOCK_DB:
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    sns      = boto3.client("sns",      region_name=AWS_REGION)

    # DynamoDB table references
    users_table    = dynamodb.Table("Users")
    bookings_table = dynamodb.Table("Bookings")
    seats_table    = dynamodb.Table("Seats")
else:
    # Mock in-memory database for demo
    users_db = {}
    bookings_db = {}
    seats_db = {}
    
    class MockTable:
        def __init__(self, db):
            self.db = db
        
        def get_item(self, Key):
            key = list(Key.values())[0]
            return {"Item": self.db.get(key, {})}
        
        def put_item(self, Item):
            key = Item[list(Key.keys())[0]]
            self.db[key] = Item
        
        def update_item(self, Key, UpdateExpression, ExpressionAttributeNames, ExpressionAttributeValues):
            key = list(Key.values())[0]
            if key in self.db:
                # Simple update for demo
                for k, v in ExpressionAttributeValues.items():
                    if k == ":cancelled":
                        self.db[key]["status"] = v
                    elif k == ":ts":
                        self.db[key]["cancelled_at"] = v
                    elif k == ":f":
                        self.db[key]["is_booked"] = v
                    elif k == ":empty":
                        self.db[key]["booked_by"] = v
        
        def scan(self, FilterExpression=None):
            return {"Items": list(self.db.values())}
    
    users_table = MockTable(users_db)
    bookings_table = MockTable(bookings_db)
    seats_table = MockTable(seats_db)
    
    # Mock SNS
    class MockSNS:
        def publish(self, TopicArn, Message, Subject):
            print(f"Mock SNS Notification: {Subject}")
            print(f"Message: {Message[:200]}...")
    
    sns = MockSNS()

# ─────────────────────────────────────────────
# SAMPLE DESTINATIONS (replace with DB in v2)
# ─────────────────────────────────────────────
DESTINATIONS = [
    {
        "id":          "dest_001",
        "name":        "Kyoto, Japan",
        "image":       "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?w=600&q=80",
        "price":       3500,
        "duration":    "7 Days",
        "seats_total": 20,
        "flight_id":   "FL-KYT-001",
        "tag":         "Culture",
    },
    {
        "id":          "dest_002",
        "name":        "Santorini, Greece",
        "image":       "https://images.unsplash.com/photo-1570077188670-e3a8d69ac5ff?w=600&q=80",
        "price":       4200,
        "duration":    "5 Days",
        "seats_total": 15,
        "flight_id":   "FL-SAN-002",
        "tag":         "Romance",
    },
    {
        "id":          "dest_003",
        "name":        "Patagonia, Chile",
        "image":       "https://images.unsplash.com/photo-1501854140801-50d01698950b?w=600&q=80",
        "price":       5500,
        "duration":    "10 Days",
        "seats_total": 12,
        "flight_id":   "FL-PAT-003",
        "tag":         "Adventure",
    },
    {
        "id":          "dest_004",
        "name":        "Marrakech, Morocco",
        "image":       "https://images.unsplash.com/photo-1539020140153-e479b8e7f7cb?w=600&q=80",
        "price":       2800,
        "duration":    "6 Days",
        "seats_total": 18,
        "flight_id":   "FL-MAR-004",
        "tag":         "Exotic",
    },
    {
        "id":          "dest_005",
        "name":        "Amalfi Coast, Italy",
        "image":       "https://images.unsplash.com/photo-1533587851505-d119e13fa0d7?w=600&q=80",
        "price":       4800,
        "duration":    "8 Days",
        "seats_total": 16,
        "flight_id":   "FL-AML-005",
        "tag":         "Scenic",
    },
    {
        "id":          "dest_006",
        "name":        "Bali, Indonesia",
        "image":       "https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=600&q=80",
        "price":       2200,
        "duration":    "7 Days",
        "seats_total": 25,
        "flight_id":   "FL-BAL-006",
        "tag":         "Relax",
    },
]

# Initialize seats for demo
if USE_MOCK_DB:
    for dest in DESTINATIONS:
        for i in range(1, dest["seats_total"] + 1):
            seat_id = f"{dest['flight_id']}_S{i:02d}"
            seats_db[seat_id] = {
                "seat_id": seat_id,
                "flight_id": dest["flight_id"],
                "is_booked": False,
                "booked_by": "",
            }

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def hash_password(password: str) -> str:
    """SHA-256 hash a password with a salt."""
    salt = "travelgo_salt_2024"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def check_password(password: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(password), hashed)

def login_required(f):
    """Decorator: redirect to login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_email" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def get_destination_by_id(dest_id: str):
    return next((d for d in DESTINATIONS if d["id"] == dest_id), None)

def get_available_seats(flight_id: str, total: int) -> list:
    """Return list of all seats with booked status from DynamoDB."""
    seats = []
    for i in range(1, total + 1):
        seat_id = f"{flight_id}-S{str(i).zfill(2)}"
        try:
            resp = seats_table.get_item(Key={"seat_id": seat_id})
            item = resp.get("Item")
            if item:
                seats.append({
                    "seat_id":     seat_id,
                    "seat_number": item.get("seat_number", f"S{str(i).zfill(2)}"),
                    "is_booked":   item.get("is_booked", False),
                    "booked_by":   item.get("booked_by", ""),
                })
            else:
                seats.append({
                    "seat_id":     seat_id,
                    "seat_number": f"S{str(i).zfill(2)}",
                    "is_booked":   False,
                    "booked_by":   "",
                })
        except ClientError:
            seats.append({
                "seat_id":     seat_id,
                "seat_number": f"S{str(i).zfill(2)}",
                "is_booked":   False,
                "booked_by":   "",
            })
    return seats

def publish_sns(subject: str, message: str):
    """Publish a notification to the SNS topic."""
    if not SNS_TOPIC_ARN:
        app.logger.warning("SNS_TOPIC_ARN not set — skipping notification.")
        return
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message,
        )
    except ClientError as e:
        app.logger.error(f"SNS publish failed: {e}")

# ─────────────────────────────────────────────
# ROUTES — AUTH
# ─────────────────────────────────────────────
@app.route("/")
def index():
    """Home page — show destinations."""
    return render_template("index.html", destinations=DESTINATIONS)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone    = request.form.get("phone", "").strip()

        # Basic validation
        if not all([name, email, password, phone]):
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("register.html")

        # Check duplicate email
        try:
            resp = users_table.get_item(Key={"email": email})
            if resp.get("Item"):
                flash("An account with this email already exists.", "danger")
                return render_template("register.html")
        except ClientError as e:
            flash(f"Database error: {e.response['Error']['Message']}", "danger")
            return render_template("register.html")

        # Write to DynamoDB
        try:
            users_table.put_item(Item={
                "email":         email,
                "name":          name,
                "password_hash": hash_password(password),
                "phone":         phone,
                "created_at":    datetime.utcnow().isoformat(),
            })
        except ClientError as e:
            flash(f"Registration failed: {e.response['Error']['Message']}", "danger")
            return render_template("register.html")

        # Welcome SNS email
        publish_sns(
            subject="Welcome to TravelGo! 🌍",
            message=(
                f"Hi {name},\n\n"
                "Welcome to TravelGo — your cloud-powered travel booking platform!\n\n"
                f"Account created for: {email}\n\n"
                "Start exploring destinations at http://<your-ec2-ip>/\n\n"
                "— The TravelGo Team"
            )
        )

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_email" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template("login.html")

        try:
            resp = users_table.get_item(Key={"email": email})
            user = resp.get("Item")
        except ClientError as e:
            flash(f"Database error: {e.response['Error']['Message']}", "danger")
            return render_template("login.html")

        if not user or not check_password(password, user["password_hash"]):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        session["user_email"] = email
        session["user_name"]  = user.get("name", email)
        flash(f"Welcome back, {user.get('name')}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ─────────────────────────────────────────────
# ROUTES — DASHBOARD
# ─────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    email = session["user_email"]
    try:
        resp     = bookings_table.scan()
        all_bookings = resp.get("Items", [])
        bookings = [b for b in all_bookings if b.get("user_email") == email]
        # Sort by timestamp descending
        bookings.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    except Exception:
        bookings = []

    # Attach destination info to each booking
    for b in bookings:
        dest = get_destination_by_id(b.get("dest_id", ""))
        b["dest_info"] = dest

    active    = [b for b in bookings if b.get("status") == "confirmed"]
    cancelled = [b for b in bookings if b.get("status") == "cancelled"]

    return render_template(
        "dashboard.html",
        bookings=bookings,
        active=active,
        cancelled=cancelled,
    )


# ─────────────────────────────────────────────
# ROUTES — BOOKING
# ─────────────────────────────────────────────
@app.route("/destination/<dest_id>")
@login_required
def destination_detail(dest_id):
    dest = get_destination_by_id(dest_id)
    if not dest:
        flash("Destination not found.", "danger")
        return redirect(url_for("index"))

    seats = get_available_seats(dest["flight_id"], dest["seats_total"])
    available_count = sum(1 for s in seats if not s["is_booked"])

    return render_template(
        "destination.html",
        dest=dest,
        seats=seats,
        available_count=available_count,
    )


@app.route("/book", methods=["POST"])
@login_required
def book():
    dest_id    = request.form.get("dest_id")
    seat_ids   = request.form.getlist("seat_ids")   # multiple seats
    user_email = session["user_email"]
    user_name  = session["user_name"]

    if not dest_id or not seat_ids:
        flash("Please select at least one seat.", "warning")
        return redirect(url_for("destination_detail", dest_id=dest_id))

    dest = get_destination_by_id(dest_id)
    if not dest:
        flash("Destination not found.", "danger")
        return redirect(url_for("index"))

    # Verify seats are still available
    for seat_id in seat_ids:
        try:
            resp = seats_table.get_item(Key={"seat_id": seat_id})
            item = resp.get("Item", {})
            if item.get("is_booked"):
                flash(f"Seat {seat_id} was just taken. Please choose another.", "danger")
                return redirect(url_for("destination_detail", dest_id=dest_id))
        except ClientError:
            pass

    # Create booking record
    booking_id = str(uuid.uuid4())
    timestamp  = datetime.utcnow().isoformat()
    total      = dest["price"] * len(seat_ids)

    try:
        bookings_table.put_item(Item={
            "booking_id":  booking_id,
            "user_email":  user_email,
            "dest_id":     dest_id,
            "destination": dest["name"],
            "flight_id":   dest["flight_id"],
            "seats":       seat_ids,
            "status":      "confirmed",
            "total_price": total,
            "timestamp":   timestamp,
        })
    except ClientError as e:
        flash(f"Booking failed: {e.response['Error']['Message']}", "danger")
        return redirect(url_for("destination_detail", dest_id=dest_id))

    # Mark seats as booked
    for seat_id in seat_ids:
        try:
            seats_table.put_item(Item={
                "seat_id":     seat_id,
                "flight_id":   dest["flight_id"],
                "seat_number": seat_id.split("-")[-1],
                "is_booked":   True,
                "booked_by":   user_email,
                "booked_at":   timestamp,
            })
        except ClientError:
            pass

    # SNS notification
    publish_sns(
        subject=f"✈ TravelGo Booking Confirmed — {dest['name']}",
        message=(
            f"Hi {user_name},\n\n"
            f"Your booking is CONFIRMED!\n\n"
            f"Destination : {dest['name']}\n"
            f"Flight ID   : {dest['flight_id']}\n"
            f"Seats       : {', '.join(seat_ids)}\n"
            f"Duration    : {dest['duration']}\n"
            f"Total Price : ${total:,}\n"
            f"Booking ID  : {booking_id}\n"
            f"Date        : {timestamp[:10]}\n\n"
            "Thank you for booking with TravelGo!\n"
            "— The TravelGo Team"
        )
    )

    flash(f"Booking confirmed! Confirmation sent to {user_email}.", "success")
    return redirect(url_for("booking_detail", booking_id=booking_id))


@app.route("/booking/<booking_id>")
@login_required
def booking_detail(booking_id):
    try:
        resp    = bookings_table.get_item(Key={"booking_id": booking_id})
        booking = resp.get("Item")
    except ClientError:
        booking = None

    if not booking or booking.get("user_email") != session["user_email"]:
        flash("Booking not found.", "danger")
        return redirect(url_for("dashboard"))

    dest = get_destination_by_id(booking.get("dest_id", ""))
    return render_template("booking_detail.html", booking=booking, dest=dest)


@app.route("/cancel/<booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    user_email = session["user_email"]
    user_name  = session["user_name"]

    try:
        resp    = bookings_table.get_item(Key={"booking_id": booking_id})
        booking = resp.get("Item")
    except ClientError as e:
        flash(f"Error: {e.response['Error']['Message']}", "danger")
        return redirect(url_for("dashboard"))

    if not booking or booking.get("user_email") != user_email:
        flash("Booking not found.", "danger")
        return redirect(url_for("dashboard"))

    if booking.get("status") == "cancelled":
        flash("This booking is already cancelled.", "info")
        return redirect(url_for("dashboard"))

    # Update booking status
    try:
        bookings_table.update_item(
            Key={"booking_id": booking_id},
            UpdateExpression="SET #s = :cancelled, cancelled_at = :ts",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":cancelled": "cancelled",
                ":ts":        datetime.utcnow().isoformat(),
            }
        )
    except ClientError as e:
        flash(f"Cancellation failed: {e.response['Error']['Message']}", "danger")
        return redirect(url_for("dashboard"))

    # Free the seats
    for seat_id in booking.get("seats", []):
        try:
            seats_table.update_item(
                Key={"seat_id": seat_id},
                UpdateExpression="SET is_booked = :f, booked_by = :empty",
                ExpressionAttributeValues={":f": False, ":empty": ""},
            )
        except ClientError:
            pass

    dest = get_destination_by_id(booking.get("dest_id", ""))
    dest_name = dest["name"] if dest else booking.get("destination", "Unknown")

    # SNS cancellation email
    publish_sns(
        subject=f"❌ TravelGo Booking Cancelled — {dest_name}",
        message=(
            f"Hi {user_name},\n\n"
            f"Your booking has been CANCELLED.\n\n"
            f"Destination : {dest_name}\n"
            f"Booking ID  : {booking_id}\n"
            f"Seats       : {', '.join(booking.get('seats', []))}\n"
            f"Refund      : ${booking.get('total_price', 0):,} (processed in 5–7 days)\n"
            f"Cancelled   : {datetime.utcnow().isoformat()[:10]}\n\n"
            "We hope to see you again soon!\n"
            "— The TravelGo Team"
        )
    )

    flash("Booking cancelled successfully. A confirmation email has been sent.", "info")
    return redirect(url_for("dashboard"))


# ─────────────────────────────────────────────
# ROUTES — API (JSON endpoints)
# ─────────────────────────────────────────────
@app.route("/api/seats/<flight_id>")
@login_required
def api_seats(flight_id):
    """Return real-time seat availability as JSON."""
    dest = next((d for d in DESTINATIONS if d["flight_id"] == flight_id), None)
    if not dest:
        return jsonify({"error": "Flight not found"}), 404
    seats = get_available_seats(flight_id, dest["seats_total"])
    return jsonify({"flight_id": flight_id, "seats": seats})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "TravelGo", "timestamp": datetime.utcnow().isoformat()})


# ─────────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Internal server error."), 500


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
