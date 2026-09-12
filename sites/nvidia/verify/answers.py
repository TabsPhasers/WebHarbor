"""Conservative deterministic fact parsing, with benign format normalization.

Recognizes compact answers and explicit fact clauses, not arbitrary prose truth.
Never uses a language model. Unsupported/ambiguous prose is a task FAIL.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import re
import unicodedata


def norm(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    text = text.translate(str.maketrans({'–': '-', '—': '-', '−': '-', '’': "'"}))
    text = re.sub(r'(?<=\d)[,\s](?=\d{3}(?:\D|$))', '', text)
    return re.sub(r'\s+', ' ', text).strip()


NUMBER = r'(?<![\w.])\d+(?:\.\d+)?(?!\w|\.\d|,\d)'
MEASURE_NUMBER = r'(?<![\w.])\d+(?:\.\d+)?(?!\d|\.\d|,\d)'
MODELS = r'(?<!\w)(?:rtx\s*(?:pro\s*)?)?(?:50[0-9]0|40[0-9]0)(?:\s*ti)?(?:\s*super)?(?!\w)|(?<!\w)(?:gh200|h200|h100|a100)(?!\w)|(?<!\w)rtx\s+(?:pro\s+)?[645]000(?:\s+(?:blackwell|ada)(?:\s+generation)?)?(?!\w)'


def models(text):
    return [re.sub(r'\s+', ' ', m.group()).removeprefix('rtx ') for m in re.finditer(MODELS, norm(text))]


def negative_measure(text, kind):
    """An explicitly negative target number is never the requested positive spec."""
    if re.search(r'(?<![\w.])\s*-\s*(?:\d|\.\d)', norm(text)):
        return True
    if kind == 'memory' and re.search(r'-\s*(?:g(?:iga)?b(?:ytes?)?)', norm(text)):
        return True
    return False


def strip_harmless_contrasts(text):
    """Remove recognised non-target clarifications so -not X- contrast with
    another model, an unrelated metric, a live-feed note or a variant name is
    not treated as denial of the requested fact. A denial of the target value
    (e.g. 'not 32 GB') is left intact for the caller to reject."""
    patterns = [
        r"\bnot\s+(?:its|the|a|an)?\s*(?:psu|power\s+supply|recommended\s+psu|"
        r"memory[- ]capacity\s+comparison|update\s+date|live\s+(?:release\s+)?feed|"
        r"real[- ]time\s+(?:release\s+)?feed|frozen\s+(?:historical\s+)?(?:catalog|catalogue|snapshot))",
        r"\bnot\s+(?:(?:an?|the)\s+)?(?:photograph|product\s+photo)",
        r"\bnot\s+(?:(?:an?|the)\s+)?\d+\s*gb\s+variant",
        r"\bnot\s+(?:(?:an?|the)\s+)?(?:canada|germany|united\s+kingdom|uk|china|japan|france|"
        r"en[- ](?:ca|gb|de|cn|jp|fr))",
        r"\bnot\s+(?:(?:an?|the)\s+)?(?:nvidia\s+)?(?:geforce\s+)?(?:rtx\s+)?(?:pro\s+)?"
        r"(?:50[0-9]0|40[0-9]0|gh200|h200|h100|a100)(?:\s*ti|\s*super)?",
        r"\bnot\s+(?:(?:an?|the)\s+)?(?:ada(?:\s+lovelace)?|blackwell|hopper|ampere|lovelace)",
        r"\bnot\s+(?:(?:an?|the)\s+)?(?:tensor|rt|ray[- ]tracing|bandwidth|memory|tdp|power|psu|"
        r"capacity|vram|installation|download|game\s+ready|studio)(?:\s+cores?|\s+rating|\s+branch|\s+capacity)?",
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text)
    return text


def model_segments(text):
    """Split a normalised answer at real model mentions.

    Returns (name, following_text_until_next_model_or_sentence) pairs so a
    fact can be bound to the model it actually describes.
    """
    normed = norm(text)
    hits = list(re.finditer(MODELS, normed))
    out = []
    for index, hit in enumerate(hits):
        end = hits[index + 1].start() if index + 1 < len(hits) else len(normed)
        piece = normed[hit.end():end]
        piece = re.split(r'(?<!\d)[.;!?](?:\s|$)', piece)[0]
        out.append((normed[hit.start():hit.end()], piece))
    return out


def names_model(name, token):
    """Whole-token model match (so h200 does not match inside gh200)."""
    return bool(re.search(r'(?<![\w.-])' + re.escape(token) + r'(?![\w-])', name))


def segment_ok(text, target, checks):
    """Bind each fact to the model it describes.

    - If the target model is named, every target mention must carry the
      expected facts; other models (a correct contrast) are ignored.
    - If only other models are named, the answer is about the wrong object.
    - If no model is named, the question supplies the object, so a bare
      value answer is checked directly (as before).
    """
    found = False
    for name, piece in model_segments(text):
        if not target(name):
            continue
        if not all(check(name + ' ' + piece) for check in checks):
            return False
        found = True
    if found:
        return True
    if model_segments(text):
        return False
    return all(check(norm(text)) for check in checks)


def only_model(text, expected):
    found = models(text)
    return bool(found) and all(m == expected for m in found)


def measurements(text, unit):
    units = {
        'memory': r'(?:g(?:iga)?b(?:ytes?)?|m(?:ega)?b(?:ytes?)?|t(?:era)?b(?:ytes?)?)',
        'power': r'(?:watts?|[km]?w)',
        'cuda': r'(?:cuda\s+cores?|tensor\s+cores?|rt\s+cores?|cores?)',
        'bandwidth': r'(?:[gmt]b\s*/\s*s|[gmt]bps|gigabytes?\s+per\s+second)',
    }
    out = []
    pattern = '(' + MEASURE_NUMBER + r')\s*(' + units[unit] + r')(?!\w)'
    for m in re.finditer(pattern, norm(text)):
        out.append((Decimal(m[1]), re.sub(r'\s+', ' ', m[2])))
    return out


def single_measure(text, value, kind):
    allowed = {'memory': {'gb', 'gbyte', 'gbytes', 'gigabyte', 'gigabytes'},
               'power': {'w', 'watt', 'watts'}, 'cuda': {'core', 'cores', 'cuda core', 'cuda cores'}}[kind]
    if negative_measure(text, kind):
        return False
    values = measurements(text, kind)
    if values:
        if kind == 'power':
            scales = {'w': 1, 'watt': 1, 'watts': 1, 'kw': 1000, 'mw': 1000000}
            return all(unit in scales and n * scales[unit] == value for n, unit in values)
        return all(n == value and unit in allowed for n, unit in values)
    # Query establishes units for a bare scalar, but an explicitly wrong unit is never ignored.
    try:
        return Decimal(norm(text).strip(' .')) == value
    except InvalidOperation:
        return False


def memory(text, value, memory_type=None):
    ok = single_measure(text, value, 'memory')
    if memory_type:
        types = re.findall(r'(?<!\w)(?:gddr\s*\d+x?|lpddr\s*\d+|hbm\s*\d+e?)(?!\w)', norm(text))
        ok = ok and bool(types) and all(t.replace(' ', '') == memory_type.casefold() for t in types)
    return ok


def price(text, amount):
    text = norm(text)
    if re.search(r'-\s*\$\s*\d', text) or re.search(r'\$\s*-\s*\d', text):
        return False
    amounts = []
    for m in re.finditer(r'(?:\$|\busd\s*)\s*(' + NUMBER + r')|(' + NUMBER + r')\s*(?:usd|us\s+dollars?|dollars?)\b', text):
        amounts.append(Decimal(m[1] or m[2]))
    return bool(amounts) and all(p == amount for p in amounts)


def version(text, expected):
    found = re.findall(r'(?<![\w.])\d{3,}\.\d+(?:\.\d+)*(?!\w|\.\d)', norm(text))
    return bool(found) and all(v == expected for v in found)


def bandwidth_values(text):
    values = measurements(text, 'bandwidth')
    result = []
    for number, unit in values:
        u = unit.replace(' ', '')
        scale = Decimal('0.001') if u.startswith('mb') else Decimal(1000) if u.startswith('tb') else Decimal(1)
        value = number * scale
        # bits/s (gbps) is not bytes/s (gb/s); 8 bits per byte.
        if 'bps' in u and '/' not in u:
            value = value / 8
        result.append(value)
    return result


def bandwidth_comparison(text, higher, lower):
    """T7: bind absolute rates to GPUs; check optional differences separately.

    Percentage tolerance is half the last reported decimal place (at most
    half a percentage point). Omitted values/explanations remain optional.
    """
    text = strip_harmless_contrasts(norm(text))
    higher, lower = Decimal(str(higher)), Decimal(str(lower))
    # A decimal in an optional explanation must not interrupt subject/winner
    # recognition in the shared bounded direction parser.
    if not direction(re.sub(r'\d+\.\d+', 'value', text), '5080', '4080 super', 'bandwidth'):
        return False
    expected = {'5080': higher, '4080 super': lower}
    model_rx = re.compile(r'\b(?:geforce\s+)?(?:rtx\s+)?(5080|4080\s+super)\b')
    rate_rx = re.compile('(' + MEASURE_NUMBER + r')\s*([gmt]b\s*/\s*s|[gmt]bps|gigabytes?\s+per\s+second)\b')
    for raw in re.split(r'[;\n]+|(?<!\d)\.(?:\s+|$)', text):
        clause = norm(raw).replace('**', '')
        rates = list(rate_rx.finditer(clause))
        models_here = list(model_rx.finditer(clause))
        for index, match in enumerate(rates):
            value = bandwidth_values(match.group())[0]
            if match.start() and clause[match.start()-1] == '-':
                value = -value
            prefix = clause[:match.start()]
            end = rates[index+1].start() if index+1 < len(rates) else len(clause)
            suffix = clause[match.end():end]
            is_delta = bool(re.search(r'\b(?:by|(?:difference|delta|gap)(?:\s+(?:is|of))?)\s*[:=]?\s*$', prefix) or
                            re.match(r'\s*(?:\([^)]*\)\s*)?(?:higher|more|greater|extra|lower|less)\b', suffix))
            if is_delta:
                if value != higher - lower:
                    return False
                continue
            # Prefer explicit postfix attribution, e.g. "736 GB/s for RTX
            # 4080 SUPER", over a different model earlier in the sentence.
            following = model_rx.search(suffix)
            owner = None
            if following and re.fullmatch(r'\s*(?:for|on|of)\s+(?:the\s+)?', suffix[:following.start()]):
                owner = re.sub(r'\s+', ' ', following[1])
            if owner is None:
                preceding = [model for model in models_here if model.end() <= match.start()]
                if preceding:
                    last = preceding[-1]
                    # Don't reuse one subject for a second unbound rate.
                    if not any(last.end() <= rate.start() < match.start() for rate in rates):
                        owner = re.sub(r'\s+', ' ', last[1])
            if owner is None or value != expected[owner]:
                return False
        for match in re.finditer('(' + MEASURE_NUMBER + r')\s*(?:%|percent\b)', clause):
            reported = Decimal(match[1])
            if match.start() and clause[match.start()-1] == '-':
                reported = -reported
            # An inverse "4080 SUPER is ... lower than 5080" uses 960 as
            # denominator, whereas the requested winner's increase uses 736.
            decreasing = bool(re.search(r'\b(?:lower|less|decrease)\b', clause))
            actual = (higher - lower) / (higher if decreasing else lower) * 100
            places = len(match[1].split('.')[1]) if '.' in match[1] else 0
            tolerance = Decimal('0.5') * (Decimal(10) ** -places)
            if abs(reported - actual) > tolerance:
                return False
    return True


def direction(text, winner, loser, metric):
    text = norm(text)
    if any(model not in (winner, loser) for model in models(text)):
        return False
    # A concise named answer is sufficient when the question supplies the metric.
    if only_model(text, winner) and re.fullmatch(r'(?:the\s+)?(?:geforce\s+)?(?:rtx\s+)?' + re.escape(winner) + r'[.!]?', text):
        return True
    if re.search(r'\b(?:equal|same|tie|neither|not|no|less|lower|fewer)\b', text):
        # The unambiguous inverse form is handled below, rather than ignoring a negative token.
        inverse = re.search(r'(?:rtx\s+)?' + re.escape(loser) + r'\b[^.;]*\b(?:less|lower|fewer)\b[^.;]*\bthan\s+(?:(?:the|geforce)\s+)*(?:rtx\s+)?' + re.escape(winner) + r'\b', text)
        if not inverse or re.search(r'\b(?:equal|same|tie|neither|not|no)\b', text):
            return False
    if metric == 'cuda' and re.search(r'\b(?:tensor|bandwidth|rt\s+cores?)\b', text):
        return False
    if metric == 'bandwidth' and re.search(r'\b(?:cuda|tensor|tdp)\b', text):
        return False
    win = r'(?:rtx\s+)?' + re.escape(winner) + r'\b'
    lose = r'(?:rtx\s+)?' + re.escape(loser) + r'\b'
    # Subject must precede its predicate without another model taking over.
    model_free = r'(?:(?!\b(?:50\d0|40\d0)\b)[^.;]){0,100}'
    positive = re.search(win + model_free + r'(?:\b(?:more|higher|greater|faster|wins|winner)\b|>)', text)
    wrong = re.search(lose + model_free + r'(?:\b(?:more|higher|greater|faster|wins|winner)\b|>)', text)
    inverse = re.search(lose + model_free + r'(?:\b(?:less|lower|fewer)\b|<)', text)
    return bool((positive or inverse) and not wrong)


def cuda_compare(text, delta):
    normed = strip_harmless_contrasts(norm(text))
    if not direction(normed, '5090', '4090', 'cuda'):
        return False
    # The question establishes CUDA for a concise answer; an explicitly wrong
    # metric is rejected by direction(), without requiring a magic CUDA token.
    numbers = re.findall(NUMBER, normed)
    if str(delta) not in numbers:
        return False
    if not all(n in {'5090', '4090', '21760', '16384', str(delta)} for n in numbers):
        return False
    # If absolute counts are given they must be attributed to the right card:
    # the first count belongs to whichever model precedes it.
    counts = [(m.start(), m.group()) for m in re.finditer(r'\b(?:21760|16384)\b', normed)]
    if counts:
        prefix = normed[:counts[0][0]]
        if '5090' in prefix and '4090' not in prefix.rsplit('5090', 1)[-1]:
            return counts[0][1] == '21760'
        if '4090' in prefix:
            return counts[0][1] == '16384'
    return True


def publication_date(text, expected):
    text = norm(text)
    # An era marker changes the date; it is not a formatting variant.
    if re.search(r'\b(?:bce|bc|ce|ad)\b', text):
        return False
    months = {name: i for i, name in enumerate(
        ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'], 1)}
    month_rx = '|'.join(m + '|' + m[:3] for m in months)
    found = []
    for m in re.finditer(r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b', text):
        found.append(tuple(map(int, m.groups())))
    for m in re.finditer(r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b', text):
        a, b, y = map(int, m.groups())
        found.append((y, b, a) if a > 12 else (y, a, b))
    for m in re.finditer(r'\b(' + month_rx + r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(\d{4})\b', text):
        month = next(v for k, v in months.items() if k.startswith(m[1]))
        found.append((int(m[3]), month, int(m[2])))
    for m in re.finditer(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(' + month_rx + r')\.?[,]?\s+(\d{4})\b', text):
        month = next(v for k, v in months.items() if k.startswith(m[2]))
        found.append((int(m[3]), month, int(m[1])))
    try:
        return bool(found) and all(date(*v).isoformat() == expected for v in found)
    except ValueError:
        return False


def jetson_compare(text):
    # Accumulate facts per product, not per mention. A table/paragraph may
    # establish capacity and identity once and later repeat a name in a summary.
    # Still validate EVERY explicit claim; a correct row cannot hide a later
    # swapped capacity, wrong identity, or reversed memory comparison.
    name_rx = re.compile(r'\b(?:jetson\s+)?(?:orin\s+)?nano\s+super\b|'
                         r'\b(?:jetson\s+)?orin\s+nx(?:\s*16\s*gb)?\b')
    kit_rx = r'\b(?:developer|development|dev)\s+kit\b'
    expected = {'nano': 8, 'nx': 16}
    facts = {key: set() for key in expected}
    active = None
    # Keep Markdown rows and sentence boundaries; norm() alone erases newlines.
    for raw in re.split(r'\n+|;|(?<!\d)[.!?](?:\s+|$)', text):
        clause = norm(raw).replace('**', '').replace('`', '')
        names = list(name_rx.finditer(clause))
        kinds = ['nano' if 'nano' in m.group() else 'nx' for m in names]
        if not names:
            # Support an immediate singular follow-up such as "It is a kit".
            if active and re.match(r'^(?:it|this product)\b', clause):
                clause = ('nano super ' if active == 'nano' else 'orin nx ') + clause
                names = list(name_rx.finditer(clause))
                kinds = [active]
            else:
                # Table headers/neutral introductions contain no asserted facts.
                if measurements(clause, 'memory') or re.search(kit_rx + r'|\bproduction module\b', clause):
                    return False  # Unbound fact: do not guess which product it describes.
                continue
        active = kinds[0] if len(set(kinds)) == 1 else None
        if len(names) >= 2:
            relation = clause[names[0].end():names[1].start()]
            if re.search(r'\b(?:twice|double|half|more|less|greater|lower|equal|same)\b', relation):
                if 'memory' not in relation or re.search(r'\b(?:not|never)\b', relation):
                    return False
                left, right = expected[kinds[0]], expected[kinds[1]]
                if re.search(r'\b(?:twice|double)\b', relation):
                    valid = left == 2 * right
                elif re.search(r'\bhalf\b', relation):
                    valid = 2 * left == right
                elif re.search(r'\b(?:more|greater)\b', relation):
                    valid = left > right
                elif re.search(r'\b(?:less|lower)\b', relation):
                    valid = left < right
                else:
                    valid = left == right
                if not valid:
                    return False
        for i, match in enumerate(names):
            kind = kinds[i]
            end = names[i+1].start() if i+1 < len(names) else len(clause)
            part = clause[match.end():end]
            opposite = r'(?:production\s+)?module' if kind == 'nano' else kit_rx
            part = re.sub(r'\bnot\s+(?:an?\s+)?' + opposite, '', part)
            if re.search(r'\b(?:not|never|maybe|perhaps)\b', part):
                return False
            claim = match.group() + ' ' + part
            values = measurements(claim, 'memory')
            if values:
                if not memory(claim, expected[kind]):
                    return False
                facts[kind].add('memory')
            types = re.findall(r'\b(?:lpddr|gddr|ddr|hbm)\s*\d+[a-z]*\b', claim)
            if any(t.replace(' ', '') != 'lpddr5' for t in types):
                return False
            kit = bool(re.search(kit_rx, part))
            module = bool(re.search(r'\bmodule\b', part))
            if kind == 'nano':
                # A kit comprises a module + carrier board; this is not a claim
                # that the kit IS a production module (even when names repeat).
                component = bool(re.search(r'\b(?:comprising|comprises|includes?|contains?|containing)\b[^|]*\bmodule\b', part))
                if re.search(r'\bproduction\s+module\b', part) or (module and not component):
                    return False
                if kit:
                    facts[kind].add('identity')
            else:
                if kit:
                    return False
                if module:
                    facts[kind].add('identity')
    return all(value == {'memory', 'identity'} for value in facts.values())


def blackwell_buying(text):
    text = strip_harmless_contrasts(norm(text))
    if not re.search(r'\bblackwell\b', text) or not re.search(r'\bnvidia\s+marketplace\b', text):
        return False
    if not re.search(r'\b(?:united\s+states|usa|u\.?s\.?a?\.?|en-us)\b', text):
        return False
    if models(text) and not only_model(text, '5080'):
        return False
    def generation(core, expected):
        names = {'tensor': r'tensor', 'rt': r'(?:rt|ray[- ]tracing)'}
        ordinal = r'(first|second|third|fourth|fifth|sixth|\d+(?:st|nd|rd|th)?)'
        gen = r'(?:gen(?:eration)?[- ]*)?'
        forward = re.findall(r'\b' + ordinal + r'[- ]*' + gen + names[core] + r'(?:\s+cores?)?\b', text)
        reverse = re.findall(r'\b' + names[core] + r'(?:\s+cores?)?\s*[:=-]?\s*(?:are\s+|is\s+|use\s+)?' + gen + ordinal + r'\b', text)
        words = dict(first=1, second=2, third=3, fourth=4, fifth=5, sixth=6)
        values = [words[v] if v in words else int(re.match(r'\d+', v)[0]) for v in forward + reverse]
        return bool(values) and all(v == expected for v in values)
    return (generation('tensor', 5) and generation('rt', 4) and
            not re.search(r'\b(?:instead|ada)\b', text) and
            not re.search(r'\bnot\s+(?:(?:the|a|nvidia)\s+)*(?:blackwell|marketplace|fifth|fourth|5th|4th|united\s+states)\b', text))
