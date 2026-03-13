"""Unit tests for safe_json_loads utility."""

from backend.utils.json_utils import safe_json_loads


class TestSafeJsonLoads:
    """Test safe_json_loads with various LLM output formats."""

    def test_plain_json_object(self):
        result = safe_json_loads('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_plain_json_array(self):
        result = safe_json_loads('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_markdown_fence_json(self):
        text = '```json\n{"action": "write_artifact", "target": "test"}\n```'
        result = safe_json_loads(text)
        assert result == {"action": "write_artifact", "target": "test"}

    def test_markdown_fence_no_lang(self):
        text = '```\n{"key": "val"}\n```'
        result = safe_json_loads(text)
        assert result == {"key": "val"}

    def test_prefix_text_before_json(self):
        text = 'Here is the result:\n{"score": 7.5, "reason": "good"}'
        result = safe_json_loads(text)
        assert result == {"score": 7.5, "reason": "good"}

    def test_prefix_text_before_array(self):
        text = "The insights are:\n[{\"content\": \"test\"}]"
        result = safe_json_loads(text)
        assert result == [{"content": "test"}]

    def test_empty_string_returns_fallback(self):
        assert safe_json_loads("") is None
        assert safe_json_loads("", fallback=[]) == []

    def test_whitespace_only_returns_fallback(self):
        assert safe_json_loads("   \n\t  ") is None

    def test_none_returns_fallback(self):
        # safe_json_loads checks `not text` first
        assert safe_json_loads(None, fallback="default") == "default"  # type: ignore

    def test_invalid_json_returns_fallback(self):
        assert safe_json_loads("not json at all") is None
        assert safe_json_loads("{broken", fallback={}) == {}

    def test_custom_fallback(self):
        assert safe_json_loads("bad", fallback={"default": True}) == {"default": True}

    def test_nested_json(self):
        text = '{"actions": [{"type": "write", "content": {"text": "hello"}}]}'
        result = safe_json_loads(text)
        assert result["actions"][0]["content"]["text"] == "hello"

    def test_json_with_unicode(self):
        text = '{"title": "基于LLM的推理优化", "score": 8.0}'
        result = safe_json_loads(text)
        assert result["title"] == "基于LLM的推理优化"
        assert result["score"] == 8.0

    def test_fence_with_extra_whitespace(self):
        text = '  \n```json\n  {"key": "val"}  \n```\n  '
        result = safe_json_loads(text)
        assert result == {"key": "val"}

    def test_fence_with_json_uppercase(self):
        text = '```JSON\n{"upper": true}\n```'
        result = safe_json_loads(text)
        assert result == {"upper": True}

    def test_multiple_fences_takes_first(self):
        text = '```json\n{"first": 1}\n```\nsome text\n```json\n{"second": 2}\n```'
        result = safe_json_loads(text)
        assert result == {"first": 1}

    def test_deepseek_style_response(self):
        """DeepSeek often wraps JSON in markdown fences with explanation."""
        text = (
            "Based on my analysis, here is the structured output:\n\n"
            "```json\n"
            '{\n'
            '  "action_type": "write_artifact",\n'
            '  "artifact_type": "review",\n'
            '  "target": "critic_review_001",\n'
            '  "content": {\n'
            '    "score": 7.5,\n'
            '    "summary": "Good progress"\n'
            '  }\n'
            '}\n'
            "```\n\n"
            "This review covers the main aspects."
        )
        result = safe_json_loads(text)
        assert result is not None
        assert result["action_type"] == "write_artifact"
        assert result["content"]["score"] == 7.5
