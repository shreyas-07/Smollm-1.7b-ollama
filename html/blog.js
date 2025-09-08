"use strict";

// ===== CLOSURE TO TRACK FORM SUBMISSIONS =====
// Create a closure to track how many times the form has been successfully submitted
const createSubmissionCounter = (() => {
    let count = 0;
    return () => {
        count++;
        console.log(`Form submission count: ${count}`);
        return count;
    };
})();

// ===== FORM VALIDATION USING ARROW FUNCTIONS =====
// Arrow function to validate blog content (more than 25 characters)
const validateBlogContent = () => {
    const blogContent = document.getElementById("blogContent").value.trim();
    if (blogContent.length <= 25) {
        alert("Blog content should be more than 25 characters");
        return false;
    }
    return true;
};

// Arrow function to validate terms and conditions checkbox
const validateTermsCheckbox = () => {
    const termsCheckbox = document.getElementById("terms");
    if (!termsCheckbox.checked) {
        alert("You must agree to the terms and conditions");
        return false;
    }
    return true;
};

// ===== FORM SUBMISSION HANDLER =====
// Add event listener to the form
document.getElementById("blogForm").addEventListener("submit", (e) => {
    e.preventDefault(); // Prevent default form submission

    // Validate blog content
    if (!validateBlogContent()) {
        return;
    }

    // Validate terms and conditions
    if (!validateTermsCheckbox()) {
        return;
    }

    // If validation passes, collect form data
    const formData = {
        blogTitle: document.getElementById("blogTitle").value.trim(),
        authorName: document.getElementById("authorName").value.trim(),
        email: document.getElementById("email").value.trim(),
        blogContent: document.getElementById("blogContent").value.trim(),
        category: document.getElementById("category").value,
        terms: document.getElementById("terms").checked
    };

    // Convert form data to JSON string and log to console
    const jsonString = JSON.stringify(formData);
    console.log("Form data as JSON string:");
    console.log(jsonString);

    // Parse the JSON string back to object for further operations
    const parsedObject = JSON.parse(jsonString);
    console.log("Parsed object:");
    console.log(parsedObject);

    // ===== OBJECT DESTRUCTURING =====
    // Extract title and email fields using object destructuring
    const { blogTitle: title, email } = parsedObject;
    console.log("Extracted using destructuring:");
    console.log("Title:", title);
    console.log("Email:", email);

    // ===== SPREAD OPERATOR =====
    // Use spread operator to add submissionDate field
    const updatedObject = {
        ...parsedObject,
        submissionDate: new Date().toISOString()
    };
    console.log("Updated object with submission date:");
    console.log(updatedObject);

    // ===== CLOSURE IN ACTION =====
    // Track submission count using closure
    createSubmissionCounter();

    // Success message
    alert("Blog published successfully!");

    // Clear the form
    document.getElementById("blogForm").reset();
    
    // Reset focus to the first field
    document.getElementById("blogTitle").focus();
});
