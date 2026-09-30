"""Focused tests for the bounded in-memory session store."""

import time

import pytest

from kavach.core.session_store import SessionLimitError, SessionNotFoundError, SessionStore


def test_store_delete_and_clear_remove_session_maps():
    store = SessionStore(max_sessions=3, max_session_bytes=1024, ttl_seconds=30)
    session_id = store.create({"[[KAVACH:PAN:0001]]": "ABCDE1234F"})

    assert store.get(session_id) == {"[[KAVACH:PAN:0001]]": "ABCDE1234F"}
    assert store.delete(session_id) is True
    with pytest.raises(SessionNotFoundError):
        store.get(session_id)

    second_id = store.create({"[[KAVACH:PAN:0001]]": "ABCDE1234F"})
    store.clear()
    with pytest.raises(SessionNotFoundError):
        store.get(second_id)


def test_store_evicts_least_recently_used_session():
    store = SessionStore(max_sessions=2, max_session_bytes=1024, ttl_seconds=30)
    first = store.create({"[[KAVACH:PAN:0001]]": "first"})
    second = store.create({"[[KAVACH:PAN:0001]]": "second"})
    store.get(first)
    third = store.create({"[[KAVACH:PAN:0001]]": "third"})

    assert store.get(first)["[[KAVACH:PAN:0001]]"] == "first"
    with pytest.raises(SessionNotFoundError):
        store.get(second)
    assert store.get(third)["[[KAVACH:PAN:0001]]"] == "third"
    store.clear()


def test_store_enforces_per_session_memory_limit():
    store = SessionStore(max_sessions=2, max_session_bytes=10, ttl_seconds=30)

    with pytest.raises(SessionLimitError):
        store.create({"[[KAVACH:PAN:0001]]": "ABCDE1234F"})


def test_store_expires_session_and_clears_its_map():
    store = SessionStore(max_sessions=2, max_session_bytes=1024, ttl_seconds=1)
    session_id = store.create({"[[KAVACH:PAN:0001]]": "ABCDE1234F"})

    time.sleep(1.1)

    with pytest.raises(SessionNotFoundError):
        store.get(session_id)
    store.clear()
