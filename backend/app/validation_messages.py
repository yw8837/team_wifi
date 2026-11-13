"""User-facing validation copy; never includes submitted values or secrets."""
import re


def message(error):
    kind = error['type']
    context = error.get('ctx', {})
    fields = error.get('loc', ())
    if fields and fields[-1] in ('email', 'contact_email'):
        return '이메일 형식을 확인해 주세요.'
    if kind == 'missing':
        return '필수 항목을 입력해 주세요.'
    if kind == 'extra_forbidden':
        return '허용되지 않은 입력 항목입니다.'
    if kind == 'string_too_short':
        return f"{context['min_length']}자 이상 입력해 주세요."
    if kind == 'string_too_long':
        return f"{context['max_length']}자 이내로 입력해 주세요."
    if kind in ('literal_error', 'enum'):
        return '목록에서 제공하는 값을 선택해 주세요.'
    if kind in ('bool_type', 'bool_parsing'):
        return '선택 항목을 확인해 주세요.'
    if kind in ('int_type', 'int_parsing', 'float_type', 'float_parsing'):
        return '올바른 숫자를 입력해 주세요.'
    if kind == 'value_error':
        # Preserve reviewed domain-specific Korean guidance, not arbitrary input.
        detail = error.get('msg', '').removeprefix('Value error, ')
        if re.search('[가-힣]', detail):
            return detail
    return '입력한 값의 형식과 허용 범위를 확인해 주세요.'
