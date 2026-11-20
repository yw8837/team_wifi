from pathlib import Path
import json
from pptx import Presentation
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path('E:/Team_Wifi')
FILE = ROOT / 'output/presentation-20261109/모두의육아_발표자료.pptx'
deck = Presentation(FILE)
assert len(deck.slides) == 36, 'Expected the reviewed 36-slide source'
original = list(deck.slides)
EMU = 9525


def text(slide, value, x, y, w, h, size=28, bold=False, color='382D29'):
    shape = slide.shapes.add_textbox(*(int(v * EMU) for v in (x,y,w,h)))
    frame = shape.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = 0
    for index, line in enumerate(value.split('\n')):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        r = p.add_run()
        r.text = line
        r.font.name = 'Malgun Gothic'
        r.font.size = Pt(size * .75)
        r.font.bold = bold
        r.font.color.rgb = RGBColor.from_string(color)
    return shape


def make_slide(title):
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor.from_string('F8F5EF')
    text(slide,title,64,43,1150,98,40,True)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,68*EMU,147*EMU,72*EMU,5*EMU)
    bar.fill.solid()
    bar.fill.fore_color.rgb = RGBColor.from_string('B94034')
    bar.line.fill.background()
    text(slide,'Team_Wifi · 데이터 분석·구현·실기기 확인 기록',68,665,1115,38,15,False,'756B65')
    text(slide,'0',1190,665,40,30,15,False,'756B65')
    return slide


answer = make_slide('육아 질문에 근거와 비교 정보를 함께 제공합니다')
text(answer,'제공 데이터 분석을 설계에 적용하고,\n공식 근거·현재 정보·사용 경험을 앱과 웹으로 연결했습니다.',72,192,1135,120,34,True)
pillars = [
    ('데이터로 선택을 돕기','관심 기준 설정\n공동 저장 조합 분석'),
    ('근거를 확인하며 답하기','공식 출처 검색\n권한 기반 현재 DB 조회'),
    ('질문과 경험을 이어가기','공구 댓글·커뮤니티\n앱·웹 저장 왕복 확인'),
]
for i,(heading,body) in enumerate(pillars):
    x=76+i*390
    text(answer,heading,x,365,350,55,28,True,'365E68')
    text(answer,body,x,435,350,110,27)
text(answer,'구현 결과를 제시하고, 이용 효과는 실제 사용자 지표로 검증합니다.',76,590,1120,55,24)
answer_notes = '저희의 답은 육아 질문에 근거와 비교 정보를 함께 제공하는 커뮤니티입니다. 제공 데이터 분석을 관심 기준과 공동 저장 분석에 적용하고, 공식 문서 검색과 현재 DB 조회를 챗봇에 연결했습니다. 사용자는 공구 댓글과 커뮤니티에서 경험을 나누고 앱과 웹에서 저장한 정보를 이어서 볼 수 있습니다. 이 세 가지가 어떻게 설계됐고 어디까지 동작을 확인했는지 근거로 설명하겠습니다.'

contents = make_slide('발표 목차')
agenda = [
    ('1  데이터가 어떤 기능으로 이어졌는가','문제 정의 · 제공 자료 · 분석 결과 · 외부 데이터','4~7장'),
    ('2  답변의 근거와 최신성을 어떻게 확보했는가','RAG · 권한 기반 DB 조회 · Opik 평가','8~9장'),
    ('3  실제 서비스에서 무엇을 확인했는가','화면 · 앱과 웹 연동 · DB · 검증 · 피드백','10~15장'),
]
for i,(heading,body,pages) in enumerate(agenda):
    y=195+i*142
    text(contents,heading,76,y,1000,50,31,True)
    text(contents,body,112,y+55,960,55,25)
    text(contents,pages,1090,y+15,120,45,24,False,'365E68')
contents_notes = '발표는 세 부분입니다. 먼저 데이터 분석이 서비스 기능으로 이어진 이유를 설명합니다. 다음으로 챗봇이 근거와 현재 정보를 확보하는 구조와 평가를 보여드립니다. 마지막으로 실제 화면, 휴대폰 연동과 검증 결과를 제시하겠습니다.'

order = [original[0], answer, contents, original[1], original[3], original[4], *original[6:15], original[2], original[5], *original[15:]]
assert len(order) == 38
ids = {s.slide_id: el for s,el in zip(deck.slides, list(deck.slides._sldIdLst))}
ordered_elements = [ids[slide.slide_id] for slide in order]
for el in list(deck.slides._sldIdLst):
    deck.slides._sldIdLst.remove(el)
for element in ordered_elements:
    deck.slides._sldIdLst.append(element)


def replace_shape_text(shape,value):
    paragraphs=shape.text_frame.paragraphs
    font=paragraphs[0].runs[0].font if paragraphs[0].runs else paragraphs[0].font
    size,bold,name=font.size,font.bold,font.name
    color=font.color.rgb if font.color.type and str(font.color.type).startswith('RGB') else RGBColor.from_string('382D29')
    shape.text=value
    for p in shape.text_frame.paragraphs:
        for run in p.runs:
            run.font.size,run.font.bold,run.font.name=size,bold,name or 'Malgun Gothic'
            run.font.color.rgb=color


titles = {
    4:'제품 조건과 사용 경험을 함께 확인할 공간이 필요합니다',
    5:'제공 자료의 발견을 비교와 저장 기능에 반영했습니다',
    6:'연관 분석 방법을 공동 저장 조합에 적용했습니다',
    7:'외부 출처와 갱신 시각으로 비교 정보를 보완합니다',
    8:'공식 근거와 현재 DB를 함께 조회해 답변합니다',
    9:'Opik으로 답변 근거와 실패 구간을 확인했습니다',
    10:'필요한 화면에서 질문하고 경험을 나눌 수 있습니다',
    11:'같은 계정의 저장이 앱과 웹에 양방향으로 반영됩니다',
    12:'같은 API와 DB에서 계정과 활동을 관리합니다',
    13:'자동 검사와 실제 기기로 구현 결과를 확인했습니다',
    14:'피드백을 기능 변경과 다음 평가 기준으로 연결했습니다',
    15:'근거를 확인하고 경험을 나누는 육아 커뮤니티',
}
seconds=[15,35,20,40,55,50,45,60,50,35,40,40,30,25,20]
assert sum(seconds)==560
mapping=[
    ('산업별 문제 정의',10,'4장 · SCQA와 보호자의 비교·근거 확인 문제'),
    ('산업 구조·데이터 이해',10,'4~5장 · 문제 맥락과 데이터 분석 단위'),
    ('문제 해결 아이디어',15,'2·7·8장 · 근거·현재 정보·사용 경험의 연결'),
    ('실무 적용 가능성',10,'10~13장 · 화면·실기기·DB·검증'),
    ('AI 선정·적용 적절성',15,'8장 · 검색·도구·소형 모델 역할 / 부록 17장 모델 비교'),
    ('AI 구현·활용 수준',15,'8~9장 · RAG와 Opik 고정 평가'),
    ('데이터 활용 기획',10,'5~8장 · 발견→기능·외부 출처 갱신'),
    ('데이터 활용 진행',5,'6·7·11장 · 분석 결과·현재 정보·실기기'),
    ('발표 구성·전달',10,'2장 답변 → 3장 목차 → 근거 → 15장 결론'),
]
for number,slide in enumerate(deck.slides,1):
    if number in titles: replace_shape_text(slide.shapes[0],titles[number])
    for shape in slide.shapes:
        if shape.has_text_frame and shape.text.strip().isdigit() and shape.left > 1100*EMU:
            replace_shape_text(shape,str(number))
    if number<=15:
        notes=slide.notes_slide.notes_text_frame.text
        import re
        notes=re.sub(r'^권장 시간 \d+초\s*','',notes)
        if number==2: notes=answer_notes
        if number==3: notes=contents_notes
        slide.notes_slide.notes_text_frame.text=f'권장 시간 {seconds[number-1]}초\n\n'+notes
    if number==4:
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text.startswith('경험을 나누는 커뮤니티에'):
                replace_shape_text(shape,'공식 근거·현재 조건·사용 경험을\n질문과 비교 동선에 연결')
    if number in [37,38]:
        t=next(s.table for s in slide.shapes if s.has_table)
        rows=mapping[:5] if number==37 else mapping[5:]+[('합계',100,'본편 10분 · 상세 근거는 부록')]
        for r,(label,points,evidence) in enumerate(rows,1):
            for c,value in enumerate([label,str(points),evidence]):
                cell=t.cell(r,c)
                cell.text=value
                for p in cell.text_frame.paragraphs:
                    for run in p.runs:
                        run.font.name='Malgun Gothic'
                        run.font.size=Pt(16)

deck.save(FILE)
notes_path=ROOT/'docs/reports/presentation-20261109/FINAL-SPEAKER-NOTES.md'
previous=notes_path.read_text(encoding='utf8')
qa=previous.split('## 예상 질문과 답변',1)[1]
qa=qa.replace('4~6장','5~6장과 부록 17장').replace('24~26장','26~28장')
body='# 모두의 육아 10분 발표 대본\n\n본편 15장, 설명 560초와 화면 전환 여유 40초로 10분을 계획했다. 사용자가 예상한 발표 시간에 맞췄으며 실제 리허설 전 기준이다. 부록은 16~38장이다. 2장에서 답을 먼저 제시하고 3장의 세 가지 목차 순서로 근거를 설명한다.\n\n'
for i,slide in enumerate(list(deck.slides)[:15]):
    body+=f'## {i+1}. {slide.shapes[0].text} · {seconds[i]}초\n\n'+slide.notes_slide.notes_text_frame.text.split('\n\n',1)[1]+'\n\n'
body+='## 예상 질문과 답변'+qa
notes_path.write_text(body,encoding='utf8')
rubric='# 중간평가 기준과 발표 근거\n\n본편 15장과 부록 23장으로 구성했다. 2장의 Answer를 중심으로 데이터 활용, RAG, 서비스 검증의 세 가지 근거를 설명한다. 설명 9분 20초에 화면 전환 여유 40초를 배정했다.\n\n| 평가항목 | 배점 | 장표 근거 |\n| --- | ---: | --- |\n'
rubric+='\n'.join(f'| {a} | {b} | {c} |' for a,b,c in mapping)
rubric+='\n| 합계 | 100 | PPTX 37~38장에도 대조표 수록 |\n\n## 발표 전 확인\n\n- 도입에서 해결책을 먼저 말한 뒤 근거 세 가지를 따라 설명한다.\n- 본편은 15장에서 마친다. 요구사항 48개와 ERD, 모델 비교는 질의응답에서 펼친다.\n- 분석 표본의 조건과 실제 이용 효과의 검증 범위를 함께 설명한다.\n- 실제 발표 시간을 재고 40초 여유 안에 화면 전환을 마친다.\n'
(ROOT/'docs/reports/presentation-20261109/EVALUATION-MAPPING.md').write_text(rubric,encoding='utf8')
(ROOT/'artifacts/presentation-final-20261109/pyramid-timing.json').write_text(json.dumps({'main':15,'appendix':23,'speaking_seconds':sum(seconds),'buffer_seconds':40,'slides':seconds},indent=2),encoding='utf8')
print('Answer-first PPTX and speaker notes updated, 38 slides, 10 minute plan')
