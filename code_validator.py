#!/usr/bin/env python3
"""
Code Validator - Validate generated code BEFORE execution

This catches wrong algorithms, syntax errors, and missing requirements
BEFORE wasting compute time running experiments.
"""

import ast
import re
from typing import Dict, Any, List, Optional


class CodeValidator:
    """
    Validate generated ML code against blueprint requirements.
    
    Checks:
    1. Required algorithm present
    2. Forbidden algorithms absent
    3. Syntactically valid Python
    4. Required imports present
    5. Accuracy print statement present
    """
    
    def __init__(self):
        pass
    
    def validate(
        self,
        code: str,
        blueprint: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate code against full blueprint.
        
        Args:
            code: Generated Python code
            blueprint: Experiment blueprint
        
        Returns:
            Dict with keys: valid (bool), errors (list), warnings (list)
        """
        required = blueprint["algorithm"]["name"]
        import_required = blueprint["algorithm"]["import"]
        forbidden = blueprint["algorithm"]["forbidden"]
        
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks_performed": []
        }
        
        # ── CHECK 1: Required algorithm present ──────────────────
        result["checks_performed"].append("required_algorithm")
        if required not in code:
            result["valid"] = False
            result["errors"].append(
                f"❌ Required algorithm '{required}' NOT found in code"
            )
        
        # ── CHECK 2: Required import present ─────────────────────
        result["checks_performed"].append("required_import")
        if import_required not in code:
            result["valid"] = False
            result["errors"].append(
                f"❌ Required import '{import_required}' NOT found"
            )
        
        # ── CHECK 3: Forbidden algorithms absent ─────────────────
        result["checks_performed"].append("forbidden_algorithms")
        for banned in forbidden:
            if banned in code:
                result["valid"] = False
                result["errors"].append(
                    f"❌ Forbidden algorithm '{banned}' FOUND in code"
                )
        
        # ── CHECK 4: Syntactically valid Python ──────────────────
        result["checks_performed"].append("syntax_valid")
        try:
            ast.parse(code)
            result["syntax_valid"] = True
        except SyntaxError as e:
            result["valid"] = False
            result["syntax_valid"] = False
            result["errors"].append(f"❌ Syntax error: {e}")
        
        # ── CHECK 5: Accuracy print present ──────────────────────
        result["checks_performed"].append("accuracy_print")
        accuracy_patterns = [
            r'print\(.*ACCURACY.*\)',
            r'print\(.*accuracy.*\.4f.*\)',
            r'print\(f.*ACCURACY.*\{.*\}.*\)'
        ]
        has_accuracy = any(
            re.search(pattern, code, re.IGNORECASE)
            for pattern in accuracy_patterns
        )
        if not has_accuracy:
            result["warnings"].append(
                "⚠️ Missing 'ACCURACY:' print - result parsing may fail"
            )
        
        # ── CHECK 6: Model instantiation present ─────────────────
        result["checks_performed"].append("model_instantiation")
        model_pattern = rf'model\s*=\s*{re.escape(required)}\('
        if not re.search(model_pattern, code):
            result["warnings"].append(
                f"⚠️ Model instantiation '{required}(...)' not found"
            )
        
        # ── CHECK 7: Train/test split present ────────────────────
        result["checks_performed"].append("train_test_split")
        if "train_test_split" not in code:
            result["warnings"].append(
                "⚠️ train_test_split not found - may overfit"
            )
        
        return result
    
    def validate_algorithm_only(
        self,
        code: str,
        required_algorithm: str,
        forbidden_algorithms: List[str]
    ) -> Dict[str, Any]:
        """
        Quick validation - check only algorithm selection.
        
        Args:
            code: Generated code
            required_algorithm: Required algorithm name
            forbidden_algorithms: List of forbidden algorithms
        
        Returns:
            Dict with valid (bool) and error (str or None)
        """
        result = {"valid": True, "error": None}
        
        if required_algorithm not in code:
            result["valid"] = False
            result["error"] = f"Required '{required_algorithm}' not found"
            return result
        
        for banned in forbidden_algorithms:
            if banned in code:
                result["valid"] = False
                result["error"] = f"Forbidden '{banned}' found"
                return result
        
        return result
    
    def extract_accuracy_from_output(self, output: str) -> Optional[float]:
        """
        Extract accuracy value from program output.
        
        Args:
            output: Program stdout
        
        Returns:
            Accuracy as float, or None if not found
        """
        # Primary pattern: ACCURACY: 0.xxxx
        match = re.search(r'ACCURACY:\s*(\d+\.\d+)', output, re.IGNORECASE)
        if match:
            return float(match.group(1))
        
        # Fallback: any decimal at end of output
        lines = output.strip().split('\n')
        if lines:
            last_line = lines[-1]
            match = re.search(r'(\d+\.\d+)', last_line)
            if match:
                return float(match.group(1))
        
        return None
    
    def get_validation_summary(self, result: Dict[str, Any]) -> str:
        """
        Get human-readable validation summary.
        
        Args:
            result: Validation result dict
        
        Returns:
            Formatted summary string
        """
        if result["valid"]:
            return "✅ Validation PASSED"
        
        lines = ["❌ Validation FAILED:"]
        for error in result["errors"]:
            lines.append(f"  {error}")
        for warning in result["warnings"]:
            lines.append(f"  ⚠️  {warning}")
        
        return "\n".join(lines)


class EscalatingPromptGenerator:
    """
    Generate increasingly forceful prompts with each retry.
    """
    
    def __init__(self, blueprint: Dict[str, Any]):
        self.blueprint = blueprint
        self.base_prompt = None  # Set by build_base_prompt()
    
    def build_base_prompt(self) -> str:
        """Build base prompt from blueprint"""
        from prompt_builder import build_qwen_prompt
        self.base_prompt = build_qwen_prompt(self.blueprint)
        return self.base_prompt
    
    def get_retry_prompt(self, attempt: int, previous_error: str) -> str:
        """
        Get prompt for retry attempt.
        
        Args:
            attempt: Which attempt (2, 3, etc.)
            previous_error: Error from previous attempt
        
        Returns:
            Escalated prompt
        """
        from prompt_builder import build_escalated_prompt
        return build_escalated_prompt(self.blueprint, attempt, previous_error)


if __name__ == "__main__":
    # Test validator
    validator = CodeValidator()
    
    # Test case 1: Valid RandomForest code
    valid_code = """
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"ACCURACY: {accuracy:.4f}")
"""
    
    test_blueprint = {
        "algorithm": {
            "name": "RandomForestClassifier",
            "import": "from sklearn.ensemble import RandomForestClassifier",
            "forbidden": ["LogisticRegression"]
        }
    }
    
    result1 = validator.validate(valid_code, test_blueprint)
    print("=== TEST 1: Valid Code ===")
    print(validator.get_validation_summary(result1))
    print(f"Checks: {result1['checks_performed']}")
    
    # Test case 2: Invalid (LogisticRegression)
    invalid_code = """
from sklearn.linear_model import LogisticRegression
model = LogisticRegression()
print(f"ACCURACY: {accuracy:.4f}")
"""
    
    result2 = validator.validate(invalid_code, test_blueprint)
    print("\n=== TEST 2: Invalid Code ===")
    print(validator.get_validation_summary(result2))
    
    # Test case 3: Extract accuracy
    output = "Training complete\nACCURACY: 0.8667"
    accuracy = validator.extract_accuracy_from_output(output)
    print(f"\n=== TEST 3: Extract Accuracy ===")
    print(f"Output: {output}")
    print(f"Extracted: {accuracy}")
