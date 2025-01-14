import json
import os
import time
from flask import Flask, render_template, request, redirect, url_for, flash
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import SpanKind
import logging
from pythonjsonlogger import jsonlogger  # Import the jsonlogger for structured logging

# Flask App Initialization
app = Flask(__name__)
app.secret_key = 'secret'
COURSE_FILE = 'course_catalog.json'

# Configure structured logging (JSON format)
log_handler = logging.StreamHandler()  # Output logs to stdout
formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
log_handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)  # Set the log level to INFO

from opentelemetry.exporter.jaeger.thrift import JaegerExporter

# Configure Jaeger exporter
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost", 
    agent_port=6831,             # Default Jaeger port
)

# Add Jaeger exporter to the tracer provider
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
trace.set_tracer_provider(tracer_provider)
FlaskInstrumentor().instrument_app(app)
tracer = trace.get_tracer(__name__)

@app.before_request
def before_request():
    """Start a span for each request."""
    request.span = tracer.start_span(
        f"{request.method} {request.path}",
        attributes={
            "http.method": request.method,
            "http.url": request.url,
        },
    )

@app.after_request
def after_request(response):
    """Close the span and log metadata."""
    request.span.set_attribute("http.status_code", response.status_code)
    if response.status_code >= 400:
        request.span.set_attribute("error", True)
    request.span.end()
    
    # Log request metadata
    logger.info("Request processed", extra={
        "method": request.method,
        "path": request.path,
        "status_code": response.status_code,
        "user_ip": request.remote_addr,
    })
    return response

# Utility Functions
def load_courses():
    """Load courses from the JSON file."""
    if not os.path.exists(COURSE_FILE):
        return []  # Return an empty list if the file doesn't exist
    with open(COURSE_FILE, 'r') as file:
        return json.load(file)

def save_courses(data):
    """Save new course data to the JSON file."""
    courses = load_courses()  # Load existing courses
    courses.append(data)  # Append the new course
    with open(COURSE_FILE, 'w') as file:
        json.dump(courses, file, indent=4)

# Routes
@app.route('/')
def index():
    """Render the home page and log the event."""
    with trace.get_tracer(__name__).start_as_current_span("Rendering Home Page") as current_span:
        current_span.set_attribute("http.method", request.method)
        current_span.set_attribute("user.ip", request.remote_addr)
        current_span.set_attribute("route", "/")
        logger.info("Successfully rendered the Home Page", extra={
            "route": "/",
            "method": request.method,
            "user_ip": request.remote_addr
        })
    return render_template('index.html')

@app.route('/catalog')
def course_catalog():
    """Render course catalog and handle new course submission."""
    with trace.get_tracer(__name__).start_as_current_span("Rendering Course Catalog"):
        current_span = trace.get_current_span()
        current_span.set_attribute("http.method", request.method)
        current_span.set_attribute("user.ip", request.remote_addr)
        current_span.set_attribute("route", "/catalog")
        logger.info("Successfully rendered the Course Catalog Page", extra={
            "route": "/catalog",
            "method": request.method,
            "user_ip": request.remote_addr
        })
    courses = load_courses()
    current_span.set_attribute("course.count", len(courses))
    current_span.set_attribute("course.names", [course['name'] for course in courses])
    return render_template('course_catalog.html', courses=courses)

@app.route('/add_courses', methods=['GET', 'POST'])
def add_courses():
    """Add a new course to the catalog."""
    with trace.get_tracer(__name__).start_as_current_span("Handling form submissions"):
        current_span = trace.get_current_span()
        current_span.set_attribute("http.method", request.method)
        current_span.set_attribute("user.ip", request.remote_addr)
        current_span.set_attribute("route", "/add_courses")

    if request.method == 'GET':
        return render_template('add_courses.html')

    if request.method == 'POST':
        course_code = request.form.get('course-code')
        course_name = request.form.get('courseName')
        instructor = request.form.get('instructor')
        semester = request.form.get('semester')
        schedule = request.form.get('schedule')
        classroom = request.form.get('classroom')
        prerequisites = request.form.get('prerequisites')
        grading = request.form.get('grading')
        description = request.form.get('Description')

        # Validate required fields
        if not course_code or not course_name or not instructor:
            missing_fields = []
            if not course_code:
                missing_fields.append("Course Code")
            if not course_name:
                missing_fields.append("Course Name")
            if not instructor:
                missing_fields.append("Instructor")
            logger.error("Missing required fields", extra={
                "missing_fields": missing_fields,
                "route": "/add_courses",
                "method": request.method,
                "user_ip": request.remote_addr
            })
            flash(f"Error: Missing required fields: {', '.join(missing_fields)}", "error")
            return redirect(url_for('course_catalog'))

        # Create course dictionary
        course = {
            "code": course_code,
            "name": course_name,
            "instructor": instructor,
            "semester": semester,
            "schedule": schedule,
            "classroom": classroom,
            "prerequisites": prerequisites,
            "grading": grading,
            "Description": description
        }

        save_courses(course)
        current_span.set_attribute("course.code", course_code)
        current_span.set_attribute("course.name", course_name)
        current_span.set_attribute("course.instructor", instructor)
        logger.info("Course added successfully", extra={
            "course_code": course_code,
            "course_name": course_name,
            "instructor": instructor,
            "route": "/add_courses",
            "method": request.method,
            "user_ip": request.remote_addr
        })
        flash("Course added successfully!", "success")
        return redirect(url_for('course_catalog'))

@app.route('/course/<code>')
def course_details(code):
    """Display details for a specific course."""
    with trace.get_tracer(__name__).start_as_current_span("Rendering Course Details"):
        current_span = trace.get_current_span()
        current_span.set_attribute("http.method", request.method)
        current_span.set_attribute("user.ip", request.remote_addr)
        current_span.set_attribute("route", f"/course/{code}")
        current_span.set_attribute("course.code", code)
        logger.info(f"Successfully rendered Course Details for {code}", extra={
            "course_code": code,
            "route": f"/course/{code}",
            "method": request.method,
            "user_ip": request.remote_addr
        })

    courses = load_courses()
    course = next((course for course in courses if course['code'] == code), None)
    if not course:
        current_span.set_attribute("error", True)
        logger.error(f"No course found with code: {code}", extra={
            "course_code": code,
            "route": f"/course/{code}",
            "method": request.method,
            "user_ip": request.remote_addr
        })
        flash(f"No course found with code '{code}'.", "error")
        return redirect(url_for('course_catalog'))

    return render_template('course_details.html', course=course)

if __name__ == '__main__':
    app.run(debug=True)
