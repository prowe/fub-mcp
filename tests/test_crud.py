"""Tests for CRUD operations on People."""

import json
import pytest
from unittest.mock import AsyncMock, patch
from fub_mcp.server import call_tool


@pytest.mark.asyncio
async def test_create_person():
    """Test creating a person."""
    args = {
        "name": "John Doe",
        "firstName": "John",
        "lastName": "Doe",
        "emails": [{"value": "john@example.com", "type": "home", "isPrimary": 1}],
        "phones": [{"value": "555-1234", "type": "mobile", "isPrimary": 1}],
        "source": "Website",
        "customFields": {
            "customClosePrice": "500000"
        }
    }
    
    with patch("fub_mcp.server.FUBClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.create_person = AsyncMock(return_value={"id": "12345", "name": "John Doe"})
        mock_client_class.return_value = mock_client
        
        result = await call_tool("create_person", args)
        assert len(result) == 1
        assert result[0].type == "text"
        
        import json
        response_data = json.loads(result[0].text)
        assert response_data["id"] == "12345"
        assert response_data["name"] == "John Doe"
        
        # Verify create_person was called with correct data
        mock_client.create_person.assert_called_once()
        call_args = mock_client.create_person.call_args[0][0]
        assert call_args["name"] == "John Doe"
        assert call_args["customFields"]["customClosePrice"] == "500000"


@pytest.mark.asyncio
async def test_update_person():
    """Test updating a person."""
    args = {
        "personId": "12345",
        "name": "John Smith",
        "customFields": {
            "customClosePrice": "600000"
        }
    }
    
    with patch("fub_mcp.server.FUBClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.update_person = AsyncMock(return_value={"id": "12345", "name": "John Smith"})
        mock_client_class.return_value = mock_client
        
        result = await call_tool("update_person", args)
        assert len(result) == 1
        
        import json
        response_data = json.loads(result[0].text)
        assert response_data["id"] == "12345"
        assert response_data["name"] == "John Smith"
        
        # Verify update_person was called correctly
        mock_client.update_person.assert_called_once()
        assert mock_client.update_person.call_args[0][0] == "12345"  # person_id
        call_args = mock_client.update_person.call_args[0][1]  # person_data
        assert call_args["name"] == "John Smith"
        assert call_args["customFields"]["customClosePrice"] == "600000"


@pytest.mark.asyncio
async def test_delete_person():
    """Test deleting a person."""
    args = {"personId": "12345"}
    
    with patch("fub_mcp.server.FUBClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.delete_person = AsyncMock(return_value={"success": True})
        mock_client_class.return_value = mock_client
        
        result = await call_tool("delete_person", args)
        assert len(result) == 1
        
        import json
        response_data = json.loads(result[0].text)
        assert response_data["success"] is True
        
        # Verify delete_person was called
        mock_client.delete_person.assert_called_once_with("12345")


@pytest.mark.asyncio
async def test_get_custom_fields():
    """Test getting custom fields."""
    with patch("fub_mcp.server.FUBClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get_custom_fields = AsyncMock(return_value={
            "customFields": [
                {"id": "1", "name": "customClosePrice", "label": "Close Price", "type": "number"},
                {"id": "2", "name": "customBuyerType", "label": "Buyer Type", "type": "dropdown"}
            ]
        })
        mock_client_class.return_value = mock_client
        
        result = await call_tool("get_custom_fields", {})
        assert len(result) == 1
        
        import json
        response_data = json.loads(result[0].text)
        assert "customFields" in response_data
        assert len(response_data["customFields"]) == 2


@pytest.mark.asyncio
async def test_get_custom_field():
    """Test getting a specific custom field."""
    args = {"customFieldId": "1"}
    
    with patch("fub_mcp.server.FUBClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get_custom_field = AsyncMock(return_value={
            "id": "1",
            "name": "customClosePrice",
            "label": "Close Price",
            "type": "number"
        })
        mock_client_class.return_value = mock_client
        
        result = await call_tool("get_custom_field", args)
        assert len(result) == 1
        
        import json
        response_data = json.loads(result[0].text)
        assert response_data["name"] == "customClosePrice"
        assert response_data["type"] == "number"


@pytest.mark.asyncio
async def test_create_note():
    """Test creating a note."""
    args = {
        "personId": "12345",
        "body": "Followed up with client and scheduled next steps."
    }
    
    with patch("fub_mcp.server.FUBClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.create_note = AsyncMock(return_value={"id": "n-123", "personId": "12345"})
        mock_client_class.return_value = mock_client
        
        result = await call_tool("create_note", args)
        assert len(result) == 1

        response_data = json.loads(result[0].text)
        assert response_data["id"] == "n-123"
        assert response_data["personId"] == "12345"
        
        mock_client.create_note.assert_called_once_with({
            "personId": "12345",
            "body": "Followed up with client and scheduled next steps."
        })


@pytest.mark.asyncio
async def test_create_note_with_optional_fields():
    """Test creating a note with optional Follow Up Boss fields."""
    args = {
        "personId": "12345",
        "subject": "Listing update",
        "body": "<p>Updated listing details.</p>",
        "isHtml": True
    }

    with patch("fub_mcp.server.FUBClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.create_note = AsyncMock(return_value={"id": "n-124", "personId": "12345"})
        mock_client_class.return_value = mock_client

        result = await call_tool("create_note", args)
        assert len(result) == 1

        response_data = json.loads(result[0].text)
        assert response_data["id"] == "n-124"

        mock_client.create_note.assert_called_once_with({
            "personId": "12345",
            "subject": "Listing update",
            "body": "<p>Updated listing details.</p>",
            "isHtml": True
        })


@pytest.mark.asyncio
async def test_create_note_requires_body_or_subject():
    """Test create_note validation when content fields are missing."""
    with patch("fub_mcp.server.FUBClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await call_tool("create_note", {"personId": "12345"})
        assert len(result) == 1

        response_data = json.loads(result[0].text)
        assert response_data.get("error") is True
        assert "body" in response_data.get("message", "")
        assert "subject" in response_data.get("message", "")
        mock_client.create_note.assert_not_called()


@pytest.mark.asyncio
async def test_create_note_rejects_empty_content():
    """Test create_note rejects empty body and subject values."""
    with patch("fub_mcp.server.FUBClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await call_tool("create_note", {"personId": "12345", "body": "   ", "subject": ""})
        assert len(result) == 1

        response_data = json.loads(result[0].text)
        assert response_data.get("error") is True
        assert "non-empty" in response_data.get("message", "")
        mock_client.create_note.assert_not_called()


@pytest.mark.asyncio
async def test_get_notes_with_sort():
    """Test getting notes with sort parameter."""
    args = {
        "personId": "12345",
        "limit": 10,
        "offset": 5,
        "sort": "-created"
    }

    with patch("fub_mcp.server.FUBClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value={"notes": [{"id": "n-1"}]})
        mock_client_class.return_value = mock_client

        result = await call_tool("get_notes", args)
        assert len(result) == 1

        response_data = json.loads(result[0].text)
        assert "notes" in response_data

        mock_client.get.assert_called_once_with(
            "/notes",
            params={"limit": 10, "offset": 5, "personId": "12345", "sort": "-created"}
        )
