from llama_stack_api import RegisterShieldRequest, Shield

# Shield for System Requirements
SYSTEM_REQ_SHIELD = RegisterShieldRequest(
    shield_id="system_req_quality_shield",
    provider_id="inline::llama-shields",
    provider_shield_id="system_requirement_validator",
    params={
        "validation_rules": [
            "check_required_fields",
            "check_vague_requirements",
            "check_consistency"
        ]
    }
)

# Shield for Software Specifications
SOFTWARE_REQ_SHIELD = RegisterShieldRequest(
    shield_id="software_spec_shield",
    provider_id="inline::llama-shields",
    provider_shield_id="software_specification_validator",
    params={
        "validation_rules": [
            "check_module_definitions",
            "check_api_completeness",
            "check_data_models"
        ]
    }
)

# Shield for Code Quality
CODE_QUALITY_SHIELD = RegisterShieldRequest(
    shield_id="code_quality_shield",
    provider_id="inline::llama-shields",
    provider_shield_id="code_quality_validator",
    params={
        "validation_rules": [
            "check_security_issues",
            "check_memory_safety",
            "check_code_structure"
        ]
    }
)