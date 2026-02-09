#!/usr/bin/env python3
"""
Firebase Token Generation Service for Cloud Run.

This service generates fresh Firebase custom tokens for workspace service accounts,
enabling secure access to Firestore with proper security rules enforcement.
"""

import logging
import os
from typing import Any

import firebase_admin
import jwt
from firebase_admin import auth, credentials
from flask import Flask, request
from google.cloud.firestore import Client as FirestoreClient


# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
try:
    # Use Application Default Credentials in Cloud Run
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(
        cred, {"projectId": os.environ.get("GCP_PROJECT", "coderd")}
    )
    logger.info("Firebase Admin SDK initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
    raise

# Initialize Firestore client
db = FirestoreClient(
    project=os.environ.get("GCP_PROJECT", "coderd"),
    database=os.environ.get("FIRESTORE_DATABASE", "onboarding"),
)


def verify_service_account_identity() -> str | None:
    """
    Verify the calling service account identity from the request.

    Cloud Run validates authentication and provides identity through
    request headers. We extract the authenticated user email from
    the X-Goog-Authenticated-User-Email header.

    Returns
    -------
    str | None
        Service account or user email if verified, None otherwise.
    """
    try:
        # First, try to get email from Cloud Run's injected header
        # Format: "accounts.google.com:service-account@project.iam.gserviceaccount.com"
        goog_email_header = request.headers.get("X-Goog-Authenticated-User-Email", "")
        if goog_email_header:
            # Strip the prefix if present
            if ":" in goog_email_header:
                email = goog_email_header.split(":", 1)[1]
            else:
                email = goog_email_header
            return email

        logger.warning("X-Goog-Authenticated-User-Email header not found")

        # Fallback: try to extract from token
        auth_header = request.headers.get("Authorization", "")

        if not auth_header or not auth_header.lower().startswith("bearer "):
            logger.warning("No valid Authorization header")
            return None

        token = auth_header.split(" ", 1)[1]

        # Decode the token (Cloud Run already validated it,
        # so we don't need to verify signature)
        decoded = jwt.decode(token, options={"verify_signature": False})

        # Extract email from token (user accounts have this, service accounts may not)
        email = decoded.get("email")

        if email:
            return email

        # For service accounts without email claim, we accept any authenticated caller
        # since Cloud Run IAM has already validated the token
        # Return a placeholder that indicates authentication succeeded
        # The actual authorization happens in get_github_handle_from_workspace_sa
        sub = decoded.get("sub")
        return f"service-account:{sub}"

    except Exception as e:
        logger.error(f"Failed to verify service account: {e}")
        return None


def get_github_handle_from_workspace_sa(service_account_email: str) -> str | None:
    """
    Map workspace service account to GitHub handle.

    Workspace naming convention: coder-{github_handle}-{workspace_name}
    Service account: {project_number}-compute@developer.gserviceaccount.com

    Since all workspaces use the same default compute SA, we need to get the
    GitHub handle from metadata or allow passing it as a parameter.

    Parameters
    ----------
    service_account_email : str
        Service account email from the workspace.

    Returns
    -------
    str | None
        GitHub handle (normalized to lowercase) if found, None otherwise.
    """
    # For now, require github_handle to be passed in request body
    # In production, you could map this via metadata or workspace labels
    github_handle = request.json.get("github_handle") if request.json else None

    if not github_handle:
        logger.warning("github_handle not provided in request")
        return None

    # Normalize GitHub handle to lowercase for case-insensitive matching
    # GitHub handles are case-insensitive but case-preserving
    github_handle_normalized = github_handle.lower()

    # Verify this participant exists in Firestore
    try:
        doc_ref = db.collection("participants").document(github_handle_normalized)
        doc = doc_ref.get()

        if not doc.exists:
            logger.warning(
                f"Participant {github_handle_normalized} not found in Firestore"
            )
            return None

        return github_handle_normalized

    except Exception as e:
        logger.error(f"Failed to verify participant: {e}")
        return None


def generate_custom_token(github_handle: str) -> tuple[bool, str | None, str | None]:
    """
    Generate a Firebase custom token for a participant.

    Parameters
    ----------
    github_handle : str
        GitHub handle of the participant.

    Returns
    -------
    tuple[bool, str | None, str | None]
        Tuple of (success, token_string, error_message).
    """
    try:
        # Create custom token with github_handle claim
        custom_token = auth.create_custom_token(
            uid=github_handle, developer_claims={"github_handle": github_handle}
        )

        # Token is returned as bytes, decode to string
        token_str = custom_token.decode("utf-8")

        return True, token_str, None

    except Exception as e:
        error_msg = f"Failed to generate token: {str(e)}"
        logger.error(error_msg)
        return False, None, error_msg


@app.route("/health", methods=["GET"])  # type: ignore[untyped-decorator]
def health() -> tuple[dict[str, str], int]:
    """Health check endpoint."""
    return {"status": "healthy"}, 200


@app.route("/generate-token", methods=["POST"])  # type: ignore[untyped-decorator]
def generate_token() -> tuple[dict[str, Any], int]:
    """
    Generate a fresh Firebase custom token for a workspace.

    Expected request body:
    {
        "github_handle": "username"
    }

    Returns
    -------
    tuple[dict, int]
        Response body and HTTP status code.
    """
    try:
        # Verify the service account identity
        service_account = verify_service_account_identity()

        if not service_account:
            return {
                "error": "Unauthorized",
                "message": "Could not verify service account identity",
            }, 401

        # Get GitHub handle from request or map from service account
        github_handle = get_github_handle_from_workspace_sa(service_account)

        if not github_handle:
            return {
                "error": "Invalid request",
                "message": "Could not determine GitHub handle. Ensure github_handle is in request body.",
            }, 400

        # Generate fresh custom token
        success, token, error = generate_custom_token(github_handle)

        if not success or not token:
            return {"error": "Token generation failed", "message": error}, 500

        return {
            "token": token,
            "github_handle": github_handle,
            "expires_in": 3600,  # 1 hour
        }, 200

    except Exception as e:
        logger.error(f"Unexpected error in generate_token: {e}")
        return {"error": "Internal server error", "message": str(e)}, 500


if __name__ == "__main__":
    # Run the Flask app
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
