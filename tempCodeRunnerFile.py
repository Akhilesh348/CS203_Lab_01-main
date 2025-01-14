import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Flask App Initialization
app = Flask(__name__)
app.secret_key = 'secret'
COURSE_FILE = 'course_catalog.json'


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
    return render_template('index.html')

@app.route('/catalog')
def course_catalog():
    """Render course catalog and handle new course submission."""
    with trace.get_tracer(__name__).start_as_current_span("Rendering Course Catalog"):
        # Add trace attributes for the user request
        current_span = trace.get_current_span()
        current_span.set_attribute("http.method", request.method)
        current_span.set_attribute("user.ip", request.remote_addr)
    courses = load_courses()
    return render_template('course_catalog.html', courses=courses)

from flask import jsonify  # Import jsonify for JSON responses

@app.route("/", methods=["GET", "POST"])
def toggle_form():
    # Determine whether to show the form
    show_form = False
    if request.method == "POST":  # Form toggle button clicked
        show_form = request.form.get("toggle_form") == "true"
    return render_template("index.html", show_form=show_form)

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/add_courses', methods=['GET', 'POST'])
def add_courses():
    """Add a new course to the catalog."""
    with trace.get_tracer(__name__).start_as_current_span("Adding New Course"):
        current_span = trace.get_current_span()
        current_span.set_attribute("http.method", request.method)
        current_span.set_attribute("user.ip", request.remote_addr)
    if request.method == 'GET':
        # Render the form page for adding courses
        return render_template('add_courses.html')

    if request.method == 'POST':
        # Handle form data submission
        course_name = request.form.get('courseName')
        instructor = request.form.get('instructor')
        semester = request.form.get('semester')
        schedule = request.form.get('schedule')
        classroom = request.form.get('classroom')
        prerequisites = request.form.get('prerequisites')
        grading = request.form.get('grading')

        # Validate required fields
        if not course_name or not instructor:
            # Log an error if fields are missing
            missing_fields = []
            if not course_name:
                missing_fields.append("Course Name")
            if not instructor:
                missing_fields.append("Instructor")
            logger.error(f"Missing required fields: {', '.join(missing_fields)}")
            
            # Notify the user
            flash(f"Error: Missing required fields: {', '.join(missing_fields)}", "error")
            return redirect(url_for('add_courses'))

        # Generate a unique course code
        courses = load_courses()
        course_code = f"C{len(courses) + 1:03d}"

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
        }

        save_courses(course)
        current_span.set_attribute("course.code", course_code)
        current_span.set_attribute("course.name", course_name)
        current_span.set_attribute("course.instructor", instructor)
        logger.info(f"Course added successfully: {course_name} by {instructor}")
        flash("Course added successfully!", "success")
        return redirect(url_for('course_catalog'))

@app.route('/course/<code>')
def course_details(code):
    """Display details for a specific course."""
    with trace.get_tracer(__name__).start_as_current_span("Viewing Course Details"):
        # Add trace attributes for the user request
        current_span = trace.get_current_span()
        current_span.set_attribute("http.method", request.method)
        current_span.set_attribute("user.ip", request.remote_addr)
        current_span.set_attribute("course.code", code)
    courses = load_courses()
    course = next((course for course in courses if course['code'] == code), None)
    if not course:
        flash(f"No course found with code '{code}'.", "error")
        return redirect(url_for('course_catalog'))
    # Add more course details to the span
    current_span.set_attribute("course.name", course["name"])
    current_span.set_attribute("course.instructor", course["instructor"])
    return render_template('course_details.html', course=course)



if __name__ == '__main__':
    app.run(debug=True)
