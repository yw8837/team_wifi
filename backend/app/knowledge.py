"""Approved public retrieval material; no community or member text enters this corpus."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import math
import re
from urllib.parse import urlsplit

from . import release
from .catalog_content import active

CORPUS_VERSION = 'approved-public-v1'
CHECKED_AT = '2026-11-06T00:00:00+00:00'
SERVICE_GUIDES = (
    ('compare-unit', '배송비와 단가 비교', '/offers', '배송비를 더한 총액과 같은 단위당 금액을 비교하세요. 구성품·용량·규격을 맞추고 별도 구매가 필요한 부속품을 확인하세요. 현재 목록에 가격이 없으면 예산에 맞는 상품이라고 판단할 수 없습니다.'),
    ('discount-gift', '증정품·사은품과 할인 조건 구분', '/calculator', '개별 포장 여부와 본품의 총 수량을 확인하세요. 증정품(사은품)의 지급 조건과 할인 적용 조건을 나누어 판매처에서 확인하세요. 단가 비교 계산기는 입력한 상품 총액과 배송비를 더해 같은 단위의 총 수량으로 나눕니다. 쿠폰·묶음 조건·반품비는 계산에 반영하지 않으며 실제 결제 금액은 판매처에서 확인하세요.'),
    ('community-guide', '커뮤니티 이용 안내', '/', '커뮤니티에서 육아 질문, 경험, 정보와 공동구매 수요를 나눌 수 있습니다. 로그인 없이 공개 글을 살펴볼 수 있고 글·댓글 작성에는 로그인이 필요합니다. 회원 경험은 의료 조언이나 검증된 제품 안전 근거가 아닙니다.'),
    ('saved-guide', '내 저장 목록과 조건 찾기', '/my/saved', '공식 목록을 저장하려면 로그인하세요. 내 저장 목록은 본인 계정에서 확인할 수 있습니다. 조건 찾기에서 관심 분야와 비교 기준을 고를 수 있습니다. 저장과 관심 표시는 구매나 주문이 아닙니다.'),
    ('scope-guide', '공식 출처와 확인 범위', '/offers', '공식 목록과 비교 안내를 제공합니다. 현재 가격·재고·호환성·KC 인증을 확인한 판매 제안이 아닙니다. 상품별 조건은 연결된 공식 출처와 제품 설명서에서 확인하세요. 실제 결제·배송·정산 기능을 제공하는 것으로 안내하지 않습니다.'),
    ('privacy-companions', '함께 저장한 목록의 근거', '/advisor', '함께 저장한 목록은 서로 다른 활성 일반 계정의 공동 저장을 집계합니다. 최소 5계정이 확인된 경우에만 공동 저장 근거를 표시하고 그보다 작으면 같은 분야의 공식 목록을 대안으로 표시합니다. 구매·매출 예측이 아닙니다.'),
    ('privacy-chat', '개인정보 없이 도우미 이용하기', '/chat', '아이의 이름·생일·사진·주소·연락처 등 개인정보를 질문에 적지 마세요. 로그인 없이 임시 대화로 이용할 수 있습니다. 대화 저장은 로그인 후 직접 선택한 경우에만 켜집니다. 저장된 대화는 마지막 저장 활동부터 30일 동안 보관하며 저장을 끄거나 대화를 종료·삭제하면 내용을 지웁니다. 승인된 공개 자료를 근거로 답하며 본인 저장·조건과 커뮤니티 글은 서버에서 현재 권한을 확인해 안내와 링크를 붙입니다.'),
    ('chat-history', '도우미 대화 저장과 삭제', '/chat', '로그인 없이 임시 대화로 이용할 수 있습니다. 로그인 후 대화 저장을 직접 선택한 경우에만 대화를 저장합니다. 마지막 저장 활동으로부터 30일 동안 보관합니다. 저장을 끄거나 대화를 종료·삭제하면 저장된 대화 내용을 지웁니다. 임시 대화는 새 로그인 후 이어볼 수 없습니다. 과거 답변은 현재 상태를 확인하는 근거가 아닙니다.'),
)


@dataclass(frozen=True)
class Chunk:
    source_id: str
    chunk_id: str
    title: str
    url: str
    source_type: str
    checked_at: str
    revision: str
    text: str
    approved_groups: tuple[str, ...] = ()
    category: str | None = None

    def citation(self, quote=None):
        return {**{k: v for k, v in asdict(self).items() if k not in {'text', 'approved_groups', 'category'}}, 'quote': quote or self.text}


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def tokens(text):
    """Korean stems are approximated by bigrams; exact words retain higher weight."""
    words = re.findall(r'[a-z0-9]+|[가-힣]+', text.casefold())
    result = set(words)
    for word in words:
        if len(word) > 2 and re.fullmatch('[가-힣]+', word):
            result.update(word[i:i+2] for i in range(len(word)-1))
    return result


def corpus():
    chunks = []
    for key, title, url, text in SERVICE_GUIDES:
        revision = digest(text)
        chunks.append(Chunk('guide:'+key, key+':'+revision[:12], title, url,
                            'service_guide', CHECKED_AT, revision, text, (text,)))
    for entry in release.catalog():
        if not active(entry):
            continue
        url = urlsplit(entry['source_url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            continue
        comparison_group = '\n'.join(entry['comparison_notes'])
        text = entry['summary'] + '\n' + comparison_group
        revision = digest(str((entry['title'], entry['source_url'], entry['source_checked_at'], text)))
        key = 'catalog:'+entry['id']
        chunks.append(Chunk(key, key+':'+revision[:12], entry['title'], entry['source_url'],
                            'catalog_comparison', entry['source_checked_at'], revision, text, (comparison_group,), category=entry['category']))
    # These checked-in summaries are already public in the discovery explanation.
    # Select only reviewed application/limitation paragraphs, never raw retail rows.
    summaries = json.loads(Path(__file__).with_name('discovery_evidence.json').read_text(encoding='utf-8'))
    for source in summaries['sources']:
        key = source['id'].lower()
        if key not in ('d1', 'd2', 'd3', 'd4'):
            continue
        detail = summaries[key]
        paragraphs = [detail.get('application', ''), detail.get('limitation', '')]
        text = '\n'.join(paragraph for paragraph in paragraphs if paragraph)
        if not text:
            continue
        revision = digest(text)
        chunks.append(Chunk('analysis:'+key, key+':'+revision[:12],
                            source['id']+' · 서비스 데이터 활용과 한계', source['url'],
                            'reviewed_analysis', CHECKED_AT, revision, text, (text,)))
    external = json.loads(Path(__file__).with_name('external_knowledge.json').read_text(encoding='utf-8'))
    for source in external['sources']:
        revision = digest(source['text'])
        key = 'guide:official-' + source['id']
        chunks.append(Chunk(key, key+':'+revision[:12], source['title'], source['url'],
                            'official_public', external['checked_at'], revision,
                            source['text'], (source['text'],)))
    return chunks


# Retrieval features are deliberately separate from tokens(), which is also used
# by the generation guard. Common Korean endings and generic service/shop terms
# must not make an unrelated catalog page eligible as factual evidence.
RETRIEVAL_STOP_WORDS = frozenset({
    '어떻게','언제','어디서','알려줘','알려주세요','보여줘','보여주세요','해줘','주세요',
    '있어','있어요','있습니다','합니다','하세요','하나요','되는','되는지','할까요','같은',
    '없이','위해','위한','대한','대해','이용','사용','확인','안내','방법','비교','기준',
    '공식','자료','정보','상품','제품','목록','육아','도우미','도움','여기','지금','현재',
})
RETRIEVAL_STOP_GRAMS = RETRIEVAL_STOP_WORDS | frozenset({
    '세요','하세','니다','습니','합니','입니','하는','하나','나요','해요','에서','으로',
    '부터','하게','하고','되고','있어','없는','없음','인지','하면','하며','이나','거나',
    '도우','우미','알려','보여','주시','드려','대한','관련','용하',
})
RETRIEVAL_SUFFIXES = tuple(sorted({
    '으로부터','에서는','에게는','하려면','하나요','할까요','해주세요','알려줘',
    '하는지','된다면','인가요','인가','이야','까지','부터','처럼','보다','에서','에게',
    '에는','으로','이나','이나요','하고','이며','하면','을','를','은','는','이','가',
    '의','에','와','과','도','만','로',
},key=len,reverse=True))


def retrieval_features(text):
    features=set()
    for raw in re.findall(r'[a-z0-9]+|[가-힣]+',text.casefold()):
        stem=raw
        for _ in range(2):
            suffix=next((suffix for suffix in RETRIEVAL_SUFFIXES
                         if stem.endswith(suffix) and len(stem)-len(suffix)>=2),None)
            if suffix is None:break
            stem=stem[:-len(suffix)]
        for word in {raw,stem}:
            if len(word)<2 or word in RETRIEVAL_STOP_WORDS:continue
            features.add('w:'+word)
            if re.fullmatch('[가-힣]+',word):
                features.update('g:'+word[index:index+2] for index in range(len(word)-1)
                                if word[index:index+2] not in RETRIEVAL_STOP_GRAMS)
    return features


def comparison_task_guide(question,documents):
    """Prefer task instructions for unbranded discount/gift comparisons."""
    if not (re.search(r'할인|쿠폰|증정|사은품',question) and
            re.search(r'비교|계산|구분|따로|나누|차이|별도|함께',question)):
        return None
    # Approved catalog headings begin with their public brand/source name.
    named_source=any(chunk.source_type=='catalog_comparison' and
                     chunk.title.split()[0].casefold() in question.casefold() for chunk in documents)
    return None if named_source else 'guide:discount-gift'


def retrieve(question, limit=5):
    categories=set(explicit_categories(question))
    query=retrieval_features(question)
    if not query:return []
    documents=corpus()
    task_guide=comparison_task_guide(question,documents)
    # Packaging/count checks are already in the task guide; retain a catalog
    # only for additional product attributes the generic guide cannot cover.
    product_specs=bool(re.search(r'묶음|팩당|총\s*매수|단계|밴드|팬티|크기|용량|규격|구성품|세트|단품|리필|소재|재질|호환|세대|세척|소독|판본|배터리|권수|모델|연식|무게|사용\s*연령',question))
    features={chunk.source_id:retrieval_features(chunk.text+' '+chunk.title) for chunk in documents}
    titles={chunk.source_id:retrieval_features(chunk.title) for chunk in documents}
    counts={term:sum(term in values for values in features.values()) for term in query}
    idf={term:math.log(1+(len(documents)-count+.5)/(count+.5)) for term,count in counts.items()}
    average=sum(map(len,features.values()))/max(1,len(documents))
    ranked=[]
    for chunk in documents:
        if task_guide and chunk.source_type=='catalog_comparison' and not (categories and product_specs):
            continue
        if categories and chunk.source_type=='catalog_comparison' and chunk.category not in categories:
            continue
        body=features[chunk.source_id]
        overlap=query & body
        words={term for term in overlap if term.startswith('w:') and idf[term]>=.65}
        grams={term for term in overlap if term.startswith('g:')}
        # A lone inflection/generic substring never admits a document. When no
        # whole stem matches, demand multiple grams with at least one rare gram.
        if not words and not (len(grams)>=2 and max((idf[term] for term in grams),default=0)>=1.2):
            continue
        score=sum(idf[term]*(2.5 if term.startswith('w:') else .45) for term in overlap)
        score+=sum(idf[term]*(1.25 if term.startswith('w:') else .2)
                   for term in query & titles[chunk.source_id])
        score/=.75+.25*len(body)/max(1,average)
        if score>=2.5:ranked.append((-score,chunk.source_id,chunk))
    ranked.sort(key=lambda row:row[:2])
    if not ranked:return []
    threshold=max(2.5,-ranked[0][0]*.25)
    selected=[row[2] for row in ranked if -row[0]>=threshold]
    if task_guide:selected.sort(key=lambda chunk:chunk.source_id!=task_guide)
    return selected[:min(5,max(0,limit))]


def revalidate(chunks):
    current = {chunk.source_id: chunk for chunk in corpus()}
    return [chunk for chunk in chunks if chunk.source_id in current and
            current[chunk.source_id].revision == chunk.revision]


def unsupported(question):
    if re.search(r'진단|치료|약물|복용|투약|해열|발열|응급|질병|처방|열이|아파|호흡|질식|의학|증상|구토|토해|설사|혈변|발진|알레르기|탈수|기침|통증|독감|경련|medical|dose|diagnos|fever', question, re.I):
        return 'medical'
    # Authentication credentials are not product certification. Remove only
    # those noun phrases; a separate KC/safety/certification request still wins.
    certification_context=re.sub(r'(?:로그인|소셜|계정|사용자|관리자|본인|이메일|휴대폰|전화번호)\s*인증(?:\s*(?:토큰|코드|번호|절차|방식))?|인증\s*토큰', '', question)
    if re.search(r'(?<![a-z])KC(?![a-z])|certif|안전하|안전해|무해|무독성|독성|안전성|인증', certification_context, re.I):
        return 'certification'
    if re.search(r'최저가|현재.?가격|지금.?가격|재고|원.?이하|만원|천원|원대|품절|재입고|구매.?가능|₩|\d+\s*원|price|stock', question, re.I):
        return 'price'
    amount_question='얼마' in question
    monetary_context=bool(re.search(r'가격|금액|비용|요금|배송비|단가|판매가|할인가|값|비싸|비싼|저렴|cost', question, re.I))
    measurement_context=bool(re.search(r'기간|기한|시간|개월|일수|주기|유효|만료|동안|수명|용량|무게|길이|높이|너비|두께|크기|개수|매수|수량|얼마\s*(?:뒤|후|전|만에)', question))
    if amount_question and (monetary_context or (re.search(r'얼마(?!나)', question) and not measurement_context)):
        return 'price'
    return None


def restricted_data_request(question):
    """A separate tool boundary for disclosure requests, not product intent."""
    query=question.casefold()
    other_principal=bool(re.search(r'(?:다른|타|타인|남의|전체|모든)\s*(?:회원|계정|사용자|사람)', query))
    if not other_principal:
        # A password-change help question does not ask for the password value.
        query=re.sub(r'(?:비밀번호|패스워드|password)(?:를|을)?\s*(?:안전하게\s*)?(?:변경|재설정|초기화|복구|설정)(?:하는|할)?\s*(?:방법|절차|안내)', '', query)
    disclosure=bool(re.search(r'출력|보여|알려|조회|열람|읽|전송|보내|넘겨|내놔|내놓|달라|가져|복사|dump|print|show|reveal|return|send|give|fetch|export', query))
    secret=bool(re.search(r'비밀번호|패스워드|password|토큰|token|(?:비밀|시크릿)\s*키|api[_\s-]?key|secret', query))
    private_field=bool(re.search(r'이메일|메일|연락처|전화번호|주소|저장|관심|조건|대화|프로필', query))
    return disclosure and (secret or (other_principal and private_field))


def timestamp():
    return datetime.now(timezone.utc).isoformat()


# Only these public category/product words can survive a prior user turn. No
# name, contact detail, number, member ID, assistant answer, or free text is copied.
CATEGORY_ALIASES={
    '기저귀·물티슈':('기저귀','물티슈'),
    '수유·이유식':('수유','이유식','젖병','젖꼭지'),
    '목욕·위생':('목욕','위생','탕온계','면봉','손톱','보관용품'),
    '외출·안전':('외출','유모차','기저귀가방','기저귀 가방','모아백'),
    '놀이·도서':('놀이','도서','그림책','사운드북','블루래빗'),
    '육아생활':('육아생활','세척','세탁','세척솔'),
}
PRODUCT_TOPICS={
    '젖병':('젖병','젖꼭지'),'기저귀':('기저귀',),'물티슈':('물티슈',),
    '유모차':('유모차',),'도서':('도서','그림책','사운드북','블루래빗'),
    '세척솔':('세척솔',),'면봉':('면봉',),'탕온계':('탕온계',),
    '보관용품':('보관용품',),'손톱 관리':('손톱',),
}


def explicit_categories(question):
    # A diaper bag belongs to outing supplies; its compound name is not a diaper request.
    bag = bool(re.search(r'기저귀\s*가방|모아백', question))
    normalized = re.sub(r'기저귀\s*가방', '외출가방', question)
    return [category for category,aliases in CATEGORY_ALIASES.items()
            if category in normalized or any(alias in normalized for alias in aliases)
            or (bag and category == '외출·안전')]


def public_topics(question):
    products=[topic for topic,aliases in PRODUCT_TOPICS.items() if any(alias in question for alias in aliases)]
    if products:return products
    domains=('기저귀','물티슈','수유','이유식','목욕','위생','외출','놀이','도서','육아생활')
    return [category for category,aliases in CATEGORY_ALIASES.items()
            if category in question or any(alias in question for alias in aliases if alias in domains)]


def latest_public_topic(user_questions):
    for question in list(user_questions)[-3:][::-1]:
        topics=public_topics(question)
        if topics:return topics[0] if len(topics)==1 else None
    return None


def resolve_public_question(question,prior_topic):
    if public_topics(question):return question,False
    if re.search(r'개인정보|로그인|대화|보관|종료|삭제|서비스|커뮤니티|가입|탈퇴',question):
        return question,False
    if not re.search(r'그거|그것|그건|그걸|그럼|그러면|그\s*(?:제품|상품|목록)|이거|이것|다른\s*(?:제품|상품|것)',question):
        return question,False
    if prior_topic is None:return question,True
    # The only addition is a server-allowlisted public noun, never history text.
    return question+'\n비교 대상: '+prior_topic,False
