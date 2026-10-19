"""Deterministic validator negative cases; no model or provider calls."""
import base64
import json
import struct
import zlib

import pytest

from services.agent_runtime.verification import (
    check_captured,
    digest,
    report,
    schema_matches,
    validate_requirements,
)


def check(kind, expected, output, ok=True):
    requirement = {'id': 'proof', 'step_id': 's', 'kind': kind, 'expected': expected}
    validate_requirements([requirement], {'s'})
    return check_captured(requirement, {'ok': ok, 'output': output}, 'receipt:fixture')


def test_exact_hash_and_schema_types():
    assert check('output_sha256', {'sha256': digest('hello')}, 'hello').verdict == 'VERIFIED'
    assert check('output_sha256', {'sha256': digest('hello')}, 'hello\n').verdict == 'FAILED'
    assert check('json_schema', {'type': 'integer'}, 'true').verdict == 'FAILED'
    assert check('json_schema', {'type': 'number'}, 'NaN').verdict == 'FAILED'
    assert check('json_schema', {'type': 'object', 'additionalProperties': False}, '{"extra":1}').verdict == 'FAILED'
    assert check('tool_succeeded', {}, 'looks good', ok=False).verdict == 'FAILED'


def test_png_header_measurement_checks_captured_bytes():
    ihdr = struct.pack('>IIBBBBB', 320, 180, 8, 2, 0, 0, 0)
    data = b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + ihdr + struct.pack('>I', zlib.crc32(b'IHDR' + ihdr) & 0xffffffff)
    output = json.dumps({'artifact_base64': base64.b64encode(data).decode()})
    assert check('artifact_properties', {'png_width': 320, 'png_height': 180, 'byte_length': len(data)}, output).verdict == 'VERIFIED'
    assert check('artifact_properties', {'png_width': 640}, output).verdict == 'FAILED'
    assert check('artifact_properties', {'png_width': 320}, '{"artifact_base64":"bad"}').verdict == 'FAILED'


def test_missing_evidence_and_incomplete_plan_never_pass():
    requirement = {'id': 'x', 'step_id': 's', 'kind': 'tool_succeeded', 'expected': {}}
    result = check_captured(requirement, None, '')
    assert result.verdict == 'UNVERIFIED'
    assert report([requirement], [check_captured(requirement, {'ok': True, 'output': ''}, 'r')], plan_completed=False)['verdict'] == 'UNVERIFIED'
    assert report([], [], plan_completed=True)['verdict'] == 'UNVERIFIED'


@pytest.mark.parametrize('expected', [{'type': 'string', 'pattern': '.'}, {'type': 'string', 'maxLength': True}, {'type': 'number', 'minimum': float('nan')}])
def test_unsupported_schema_or_nonfinite_bounds_rejected(expected):
    with pytest.raises(ValueError):
        validate_requirements([{'id': 'x', 'step_id': 's', 'kind': 'json_schema', 'expected': expected}], {'s'})


def test_structural_schema_recurses():
    assert schema_matches([{'x': 2}], {'type': 'array', 'items': {'type': 'object', 'required': ['x'], 'properties': {'x': {'type': 'integer'}}}})
    assert not schema_matches([{'x': '2'}], {'type': 'array', 'items': {'type': 'object', 'properties': {'x': {'type': 'integer'}}}})


@pytest.mark.parametrize('field', ['step_id', 'kind'])
@pytest.mark.parametrize('value', [{}, [], None, 1])
def test_malformed_checker_fields_are_validation_errors(field, value):
    item = {'id': 'x', 'step_id': 's', 'kind': 'tool_succeeded', 'expected': {}}
    item[field] = value
    with pytest.raises(ValueError):
        validate_requirements([item], {'s'})
