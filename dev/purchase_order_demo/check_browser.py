"""Local Edge/Chrome CDP check; requires running servers and port 9223."""
import base64
import json
from pathlib import Path
import time
import urllib.request

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)


class Browser:
    def __init__(self, url):
        self.connection = connect(url, max_size=30_000_000)
        self.ws = self.connection.__enter__()
        self.sequence = 0

    def command(self, name, **params):
        self.sequence += 1
        self.ws.send(json.dumps({"id": self.sequence, "method": name, "params": params}))
        while True:
            result = json.loads(self.ws.recv(timeout=40))
            if result.get("id") == self.sequence:
                if "error" in result:
                    raise AssertionError(result["error"])
                return result.get("result", {})

    def js(self, expression):
        result = self.command("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        if result.get("exceptionDetails"):
            raise AssertionError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def wait(self, expression):
        until = time.monotonic() + 40
        while time.monotonic() < until:
            if self.js(expression):
                return
            time.sleep(0.2)
        raise AssertionError("Browser condition timed out: " + expression)

    def screenshot(self, name):
        screenshot = self.command("Page.captureScreenshot", format="png")
        (ARTIFACTS / name).write_bytes(base64.b64decode(screenshot["data"]))


BUTTON = "(text, root=document) => { const b=[...root.querySelectorAll('button')].find(e=>e.textContent.includes(text)); if(!b||b.disabled) throw Error('Button unavailable: '+text); b.click(); }"
SESSION = "fetch('/api/demo/purchase-orders/session').then(r=>r.json())"
CARD = "document.querySelector('[data-review-row=\"ROW\"]')"


def button(browser, text, root="document"):
    browser.js(f"({BUTTON})({json.dumps(text)}, {root})")


def customer(browser, sample):
    browser.js("([...document.querySelectorAll('.po-customer-tabs button')].find(b=>b.querySelector('b').textContent===" + json.dumps(sample) + ")).click()")
    browser.wait("document.querySelector('.po-result-pane').textContent.includes(" + json.dumps(sample + " 거래처 개별 출력") + ")")


def row_change(browser, row, code):
    revision = browser.js(f"(async()=> (await ({SESSION})).revision)()")
    card = CARD.replace("ROW", str(row))
    browser.js(f"(()=>{{const card={card}; if(!card)throw Error('Missing result row'); const tools=card.nextElementSibling; {code} }})()")
    browser.wait(f"(async()=> (await ({SESSION})).revision > {revision})()")
    browser.wait("!document.body.textContent.includes('서버에서 재검증 중')")


def choose_item(browser, row, item):
    row_change(browser, row, "const select=card.querySelector('select');select.value=" + json.dumps(item) + ";select.dispatchEvent(new Event('change',{bubbles:true}));")


def confirm_amount(browser, row):
    card = CARD.replace("ROW", str(row))
    browser.js(f"({card}).querySelector('input[type=checkbox]').click()")
    row_change(browser, row, f"({BUTTON})('금액 확정',card);")


def downloaded(browser, folder, sample):
    button(browser, "검수 완료 XLSX")
    path = folder / f"statement_{sample}.xlsx"
    until = time.monotonic() + 15
    while not path.exists() and time.monotonic() < until:
        time.sleep(.2)
    assert path.exists(), "No browser download for " + sample
    return path


def main():
    targets = json.load(urllib.request.urlopen("http://127.0.0.1:9223/json/list", timeout=5))
    target = next(t for t in targets if t["type"] == "page" and "/demo/purchase-orders" in t["url"])
    browser = Browser(target["webSocketDebuggerUrl"])
    browser.command("Page.enable")
    browser.command("Page.navigate", url="http://127.0.0.1:3000/demo/purchase-orders")
    time.sleep(1)
    browser.wait("document.readyState==='complete' && !document.getElementById('workspace')")
    browser.command("Emulation.setDeviceMetricsOverride", width=1440, height=1050, deviceScaleFactor=1, mobile=False)
    downloads = ARTIFACTS / f"download-{time.time_ns()}"
    downloads.mkdir()
    browser.command("Browser.setDownloadBehavior", behavior="allow", downloadPath=str(downloads.resolve()))
    browser.wait("document.body.textContent.includes('우리 회사의 동일한 거래명세서 양식으로.')")
    assert browser.js("document.querySelectorAll('.po-thumbnail img').length") == 3
    assert browser.js("document.querySelectorAll('.po-separate-files span').length") == 3
    button(browser, "A/B/C 전체 체험")
    browser.wait("!document.body.textContent.includes('서버에서 재검증 중') && document.body.textContent.includes('39행') && document.body.textContent.includes('134,640원')")
    browser.js("window.scrollTo(0,0)")
    initial = browser.js(f"(async()=> (await ({SESSION})).summary)()")
    assert initial == {"source_rows": 39, "accepted": 29, "review": 7, "canceled": 3}
    assert not browser.js("document.body.textContent.includes('확인 필요 행 해결')")
    assert browser.js("document.querySelectorAll('.po-row-tools').length") == 0
    columns = browser.js("[...document.querySelectorAll('.po-statement-table thead th')].map(e=>e.textContent)")
    assert columns == ["순번","품목코드","표준품명","단위","수량","단가","공급가액","부가세","합계"], columns
    assert browser.js("document.querySelector('.po-amount-summary').textContent.includes('134,640원')")
    bounds = browser.js("['po-source-panel','po-result-panel'].map(id=>{const b=document.getElementById(id).getBoundingClientRect();return {x:b.x,y:b.y,w:b.width}})")
    assert bounds[0]["x"] + bounds[0]["w"] <= bounds[1]["x"] and abs(bounds[0]["y"]-bounds[1]["y"]) < 2
    assert browser.js("document.querySelectorAll('.po-data-row').length") == 10
    assert browser.js("document.querySelectorAll('.po-data-row[data-row-state=review]').length") == 2
    assert browser.js("[...document.querySelectorAll('button')].find(b=>b.textContent.includes('검수 완료 XLSX')).disabled")
    button(browser, "확인 필요", "document.querySelector('.po-filter-bar')")
    browser.wait("document.querySelectorAll('.po-data-row').length===2")
    assert browser.js("document.querySelectorAll('.po-problem-cell[data-problem=true]').length") >= 2
    browser.js("document.getElementById('workspace').scrollIntoView()")
    button(browser, "전체", "document.querySelector('.po-filter-bar')")
    browser.screenshot("desktop-current.png")
    card = CARD.replace("ROW","15")
    browser.js(f"(()=>{{const input=({card}).querySelector('input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'5');input.dispatchEvent(new Event('input',{{bubbles:true}}));}})()")
    row_change(browser, 15, f"({BUTTON})('적용·재검증',card);")
    browser.wait("document.querySelector('[data-total=\"144540\"]')!==null")
    assert browser.js("document.querySelectorAll('.po-data-row').length") == 10
    assert browser.js("document.querySelectorAll('.po-data-row[data-row-state=review]').length") == 1
    confirm_amount(browser, 19)
    browser.wait("document.querySelector('[data-total=\"159390\"]')!==null")
    a_file = downloaded(browser, downloads, "A")

    customer(browser, "B")
    browser.wait("document.querySelector('[data-total=\"121550\"]')!==null")
    assert browser.js("document.querySelectorAll('.po-data-row').length") == 11
    button(browser, "제외", "document.querySelector('.po-filter-bar')")
    browser.wait("document.querySelectorAll('.po-data-row').length===3")
    assert browser.js("[...document.querySelectorAll('.po-data-row')].every(r=>r.dataset.rowState==='canceled')")
    button(browser, "전체", "document.querySelector('.po-filter-bar')")
    browser.js("document.querySelector('[aria-label=\"원본 2·4·8행 상세\"]').click()")
    browser.js("document.querySelector('.po-trace summary').click()")
    browser.wait("document.body.textContent.includes('원본 2·4·8행 / 수량 3+5+4=12') && document.body.textContent.includes('수량 G8')")
    assert not browser.js("document.querySelector('.po-trace').textContent.includes('quantity:')")
    before = browser.js("document.getElementById('po-result-panel').clientWidth")
    button(browser, "원본 접기")
    browser.wait("document.getElementById('po-result-panel').clientWidth > " + str(before))
    button(browser, "원본 펼치기")
    button(browser, "확대 보기")
    browser.wait("document.querySelector('dialog').open")
    assert browser.js("document.querySelector('dialog .po-source-scroll').clientWidth > document.querySelector('#po-source-panel .po-source-scroll').clientWidth")
    button(browser, "닫기 ×", "document.querySelector('dialog')")
    dimensions = browser.js("(()=>{const s=document.querySelector('[aria-label=\"거래처 B 원본 가로 스크롤 표\"]');return {scroll:s.scrollWidth,client:s.clientWidth,font:getComputedStyle(s.querySelector('table')).fontSize}})()")
    assert dimensions["scroll"] > dimensions["client"] and dimensions["font"] == "14px", dimensions
    choose_item(browser, 13, "S010")
    browser.wait("document.querySelector('[data-review-row=\"13\"]').textContent.includes('2,400원')")
    confirm_amount(browser, 13)
    choose_item(browser, 9, "S004")
    browser.wait("document.querySelector('[data-review-row=\"9\"]').textContent.includes('8,500원')")
    confirm_amount(browser, 9)
    b_file = downloaded(browser, downloads, "B")
    browser.js("document.getElementById('workspace').scrollIntoView()")


    customer(browser, "C")
    c_dates = browser.js(f"(async()=> (await ({SESSION})).orders.find(o=>o.sample==='C').lines.map(l=>l.due))()")
    assert set(c_dates) == {"2026-11-09","2026-11-12"}
    for row in [15,21,24]:
        card = CARD.replace("ROW",str(row))
        browser.js(f"({card}).querySelector('.po-error-actions button').click()")
        browser.js(f"(()=>{{const tools=({card}).nextElementSibling;const input=tools.querySelector('textarea');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,'거래처 확인 전 이번 발행 제외');input.dispatchEvent(new Event('input',{{bubbles:true}}));}})()")
        row_change(browser, row, f"({BUTTON})('사유 기록 후 제외',tools);")
    assert browser.js("document.querySelectorAll('.po-data-row').length") == 11
    assert browser.js("document.querySelectorAll('.po-data-row[data-row-state=excluded]').length") == 3
    button(browser, "확인 필요", "document.querySelector('.po-filter-bar')")
    browser.wait("document.querySelector('.po-empty-result')!==null")
    button(browser, "제외", "document.querySelector('.po-filter-bar')")
    browser.wait("document.querySelectorAll('.po-data-row').length===3")
    assert browser.js("document.querySelector('.po-data-row').textContent.includes('제외 사유')")

    button(browser, "전체", "document.querySelector('.po-filter-bar')")
    c_file = downloaded(browser, downloads, "C")

    import sys
    sys.path.insert(0, str(ROOT.parents[1]))
    from backend.order_xlsx import read_sheets
    from decimal import Decimal
    server_totals = browser.js(f"(async()=> Object.fromEntries((await ({SESSION})).orders.map(o=>[o.sample,o.totals.total])))()")
    customers = []
    for path in (a_file,b_file,c_file):
        sheets = read_sheets(path)
        main_sheet = next(iter(sheets.values()))["cells"]
        assert [main_sheet[f"{chr(65+i)}9"] for i in range(9)] == columns
        assert main_sheet["I31"] == Decimal(server_totals[path.stem[-1]])
        customers.append(main_sheet["B4"])
    assert len(set(customers)) == 3

    browser.command("Emulation.setDeviceMetricsOverride", width=390,height=844,deviceScaleFactor=1,mobile=True)
    browser.js("window.scrollTo(0,0)")
    browser.wait("window.innerWidth===390")
    assert browser.js("getComputedStyle(document.getElementById('po-source-panel')).display==='none'")
    assert browser.js("getComputedStyle(document.getElementById('po-result-panel')).display!=='none'")
    browser.js("document.getElementById('po-source-tab').click()")
    browser.wait("getComputedStyle(document.getElementById('po-result-panel')).display==='none'")
    assert browser.js("getComputedStyle(document.getElementById('po-source-panel')).display!=='none'")
    browser.js("document.getElementById('workspace').scrollIntoView()")

    browser.js("document.getElementById('po-result-tab').click()")
    browser.wait("getComputedStyle(document.getElementById('po-source-panel')).display==='none'")
    assert browser.js("document.documentElement.scrollWidth<=window.innerWidth"), "Mobile page overflow"
    # Start a fresh session to exercise pending cards at mobile size.
    button(browser, "A/B/C 전체 체험")
    browser.wait("!document.body.textContent.includes('서버에서 재검증 중') && document.querySelector('.po-result-pane').textContent.includes('A 거래처 개별 출력') && document.querySelector('[data-review-row=\"15\"][data-row-state=review]')!==null")
    browser.js("document.getElementById('workspace').scrollIntoView()")
    assert browser.js("getComputedStyle(document.querySelector('.po-data-row')).display==='grid'")
    assert browser.js("document.querySelector('.po-result-scroll').scrollWidth<=document.querySelector('.po-result-scroll').clientWidth")
    assert browser.js("[...document.querySelectorAll('.po-data-row')].every(r=>r.getBoundingClientRect().right<=window.innerWidth)")
    assert browser.js("(()=>{const r=document.querySelector('[data-review-row=\"15\"]');return ['.po-item-name','.po-state-badge','.po-cell-quantity','.po-cell-supply','.po-mobile-edit'].every(s=>r.querySelector(s).getBoundingClientRect().width>0)})()")
    browser.js("document.querySelector('.po-data-row').scrollIntoView({block:'start'})")
    browser.screenshot("mobile-current.png")
    browser.js("document.querySelector('[data-review-row=\"15\"] .po-mobile-edit').click()")
    browser.js("(()=>{const input=document.querySelector('[aria-label=\"15행 수량\"]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'5');input.dispatchEvent(new Event('input',{bubbles:true}));})()")
    row_change(browser,15,f"({BUTTON})('적용·재검증',card);")
    browser.wait("document.querySelector('[data-total=\"144540\"]')!==null")
    assert browser.js("document.querySelector('.po-result-scroll').scrollWidth<=document.querySelector('.po-result-scroll').clientWidth")

    version = json.load(urllib.request.urlopen("http://127.0.0.1:9223/json/version",timeout=5))
    control = Browser(version["webSocketDebuggerUrl"])
    context = control.command("Target.createBrowserContext")["browserContextId"]
    second_target = control.command("Target.createTarget",url="http://127.0.0.1:3000/demo/purchase-orders",browserContextId=context)["targetId"]
    targets = json.load(urllib.request.urlopen("http://127.0.0.1:9223/json/list",timeout=5))
    other = Browser(next(t for t in targets if t["id"]==second_target)["webSocketDebuggerUrl"])
    other.wait("document.body.textContent.includes('A/B/C 전체 체험')")
    assert other.js("fetch('/api/demo/purchase-orders/session').then(r=>r.status)") == 401
    other.ws.close()
    control.command("Target.disposeBrowserContext",browserContextId=context)
    report = {"status":"passed","initial":initial,"b_preview":dimensions,"statement_columns":columns,"downloads":[str(p) for p in (a_file,b_file,c_file)],
              "checks":["source thumbnails to common format","desktop side-by-side","same nine XLSX columns for A/B/C","pending rows stay in result","problem cells and status text/icons",
                        "inline quantity/master/amount/exclusion","immediate server totals","all/review/excluded filters","all B source cells","separate customer downloads",
                        "390px source/result tabs and compact cards","mobile inline quantity edit","collapsed source and enlarged dialog","Korean aggregated provenance","isolated browser context"]}
    (ARTIFACTS/"browser-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    browser.command("Browser.close")


if __name__=="__main__":
    main()
