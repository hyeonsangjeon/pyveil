# pyveil — 2차 폴리싱 피드백 (Round‑2 Polish Feedback)

> **작성자**: Claude Opus 4.8 (agent)
> **작성일**: 2026‑06‑27
> **대상 실행자**: codex (이 문서를 읽고 직접 설치·판단·구현)
> **선행 문서**: `2026-06-27-opus-round2-polish-request.md` (request) → 본 문서는 그 **응답(feedback)**
> **목표**: skeleton 상태의 pyveil 을 **"한눈에 WOW" 나는 awesome 등급 OSS** 로 끌어올리기 위한,
> 증거 기반·우선순위화된·실행 가능한 폴리싱 지침서.

---

## 0. TL;DR — 한눈에 보기

| 항목 | 현재 | 목표 | 격차 |
|---|---|---|---|
| **등급** | 🟥 **D (skeleton)** | 🟩 **A+ (awesome)** | 매우 큼 |
| 코어 구현 | 0% (전부 docstring stub) | 100% | 전량 구현 필요 |
| `import` 동작 | ❌ `ModuleNotFoundError: veil.masker` | ✅ | **P0 블로커** |
| 테스트 | ❌ 수집 단계 실패 (collection error) | ✅ ≥90% cov | 전량 |
| 패키지 네이밍 | ⚠️ `pyveil/`(dist) vs `veil`(import) **분열** | 단일화 | **P0 블로커** |
| 문서/CI/훅 | 없음 | 풀세트 | 전량 |

**지금 당장 막고 있는 5가지 (P0 블로커)**
1. **패키지 이름 분열** — 디렉터리는 `pyveil/`, 테스트는 `import veil`. 하나로 통일해야 아무것도 안 돌아감.
2. **코어 미구현** — `masker.py`, `patterns.py`, `utils.py`, `meta.py` 전부 빈 docstring. `mask_pii` 부재.
3. **pytest 기본 실행 불가** — `pyproject.toml` 의 `addopts` 가 `--cov` 를 강제 → `pytest-cov` 없으면 즉시 에러.
4. **`py.typed` 누락** — 패키징은 typed 라고 선언하는데 마커 파일이 없음(거짓 선언).
5. **죽은 참조/메타 placeholder** — `MANIFEST.in` 의 `CLAUDE.md`(없음), `yourusername`, `your.email@example.com`.

> ⏱️ **추천 진행 순서**: §3 (P0) → §4 (P1) → §5 (P2). P0 를 끝내면 "녹색 테스트"라는 심리적 모멘텀이 생긴다.

---

## 1. 현재 상태 스냅샷 (Baseline — 전부 실측)

### 1.1 파일 인벤토리 (worktree, 커밋된 트리)
```
pyveil/__init__.py     4 lines  (버전/저자 메타만)
pyveil/masker.py       1 line   (""" docstring """ 만)
pyveil/patterns.py     1 line   (stub)
pyveil/utils.py        1 line   (stub)
tests/test_masker.py   1 line   (stub)
tests/test_patterns.py 1 line   (stub)
tests/test_utils.py    1 line   (stub)
examples/basic_usage.py 1 line  (stub)
docs/README.md         (Quick Start 이후 잘림)
README.md              (## Features 이후 잘림)
```

### 1.2 메인 체크아웃의 WIP (`/Users/hyeonsang/git/veil`, **untracked**)
> ⚠️ 아래는 아직 커밋되지 않은 작업본이다. codex 는 이 방향성을 **정본으로 채택**하고 정리/구현해야 한다.
```
veil/meta.py            (docstring stub, __init__.py 없음 → 아직 패키지 아님)
tests/test_masker.py    116줄, 실제 동작 계약 정의 (아래 §2)
tests/test_pipeline.py  stub (detect→mask→recompose E2E 의도)
tests/test_meta.py      stub (manage_pii_meta 의도)
a.txt                   빈 파일 (제거 대상)
local.data/mask/*.java  마스킹 레퍼런스 (telecom 급, 아래 §2.3)
```

### 1.3 실측 명령 결과 (증거)
```text
$ python3 -c "import pyveil; print(pyveil.__version__, dir(...))"
version: 0.1.0
public API: []            # ← __init__ 이 아무것도 export 안 함

$ python3 -m pytest tests/ -o addopts="" -q
ModuleNotFoundError: No module named 'veil.masker'   # ← 수집 단계에서 폭사

$ ruff check .
warning: top-level linter settings are deprecated (select/ignore → lint.*)
W292 No newline at end of file  (pyveil/__init__.py:5)
```

### 1.4 환경
- Python **3.11.7**. 설치됨: `pip 26.1`, `pytest 9.0.2`, `ruff 0.14.2`.
- 미설치: `black`, `mypy`, `pre-commit`, `twine`, `build` → CI/훅 도입 시 명시 설치 필요.

### 1.5 PyPI 사실관계 (네이밍 의사결정용)
- `pyveil` 0.1.0 → **이미 사용자 본인이 게시함** (summary/URL 동일, `yourusername/pyveil`). ⇒ **배포명 `pyveil` 유지.**
- `veil` → 빈 placeholder(v0) 가 선점. ⇒ **배포명으로는 못 씀.** (단, *import* 이름과 PyPI 배포명은 별개라 import 로는 `veil` 사용 가능.)

---

## 2. 설계 의도 복원 (Recovered Design Intent)

빈 stub 들 뒤에 숨은 "원래 만들려던 것" 을 WIP 테스트 + Java 레퍼런스로부터 역설계했다.
codex 는 아래 계약을 **그대로 구현**하면 된다 (테스트가 곧 스펙).

### 2.1 핵심 API 계약 (from `tests/test_masker.py`)
```python
from veil.masker import mask_pii   # ← import 경로 결정 필요 (§3.1)

items = [
    {"text": "user.name@dummy-domain.test", "type": "email", "start": 0, "end": 27},
    ...
]
result = mask_pii(items, level="hi")   # level ∈ {"hi","mid","low"}
# 반환: 입력 dict + "masked_text" 키가 추가된 list[dict]
result[0]["masked_text"]   # 예: "u***@dummy-domain.test"
```

- **입력**: PII 조각(span) 리스트. 각 항목 `{text, type, start, end}`.
- **출력**: 동일 리스트 + 항목별 `masked_text`.
- **레벨**: `hi`(가장 강하게 가림) → `mid` → `low`(가장 약하게). Java 의 `HI/MI/LO` 에 대응.

### 2.2 타입 × 레벨 행동 매트릭스 (테스트가 강제하는 불변식)
| type | `hi` (강) | `mid` (중) | `low` (약) |
|---|---|---|---|
| **email** | `@` 는 유지, local 가림 | 첫 글자 유지 (`u…`) | 첫 글자 유지 (`u…`) |
| **phone** | `*` 포함 (대부분 가림) | 끝 4자리 유지 (`…2222`) | 국가코드 유지 (`+99…`) |
| **name** | `*` 포함 | 첫 이니셜 유지 (`A…`) | 공백(구조) 유지 |
| **address** | `*` 포함 | 도시 유지 (`…City`) | 도로 토큰 유지 (`…Rd`) |
| **credit_card** | `*` 포함 | 끝 4자리 유지 (`…6666`) | 앞 4자리 유지 (`9999…`) |

> 위 표의 각 칸은 `tests/test_masker.py` 의 `assert` 와 1:1 대응한다. **구현이 곧 이 표를 만족시키면 통과.**

### 2.3 Java 레퍼런스 → Python 매핑 (`local.data/mask/`)
레퍼런스는 통신사 급 마스킹 엔진이다. 핵심 개념만 추리면:

- **포맷 타입 `HI / MI / LO / RW / FF`**
  - `HI` = 최강 마스킹, `MI` = 중간, `LO` = 최소, `RW` = raw(미가림), `FF` = 폴백(`****`).
  - Python `level` 의 `hi/mid/low` 가 `HI/MI/LO` 에 대응. (`RW/FF` 는 Python 에선 옵션/예외 처리로 흡수)
- **룰 조회 구조** (`MaskFilter` + `MaskingRuleMapper` + `MaskingRuleCDTO`)
  - 마스킹코드 → `(useYn, rlseYn, fmtTp)` 캐시 조회 후 포맷 결정. 에러 시 항상 `****` 폴백.
  - ➡️ Python 에선 과한 구조. **타입→마스커 함수 디스패치 + level 인자** 로 단순화 권장.
- **타입별 포맷 규칙** (`MaskFormat.java`, 발췌)

| Java 메서드 | 의미 | HI | MI | LO |
|---|---|---|---|---|
| `maskEmail` | 이메일 | 앞4 + 나머지 가림 | local 전체 가림 + `@domain` | 앞2 + local 가림 + `@domain` |
| `maskCustNm` | 이름 | 앞1 + 가림 | 앞2 + 가림 | 앞1 + 중간가림 + 끝1 |
| `maskSvcNum` | 전화 | 중간/끝 강하게 `*`, dash 유지 | 중간만 `*` | 최소 `*` |
| `maskCardNum` | 카드 | 전부 가림(라벨) | 전부 가림 | 앞4 + 나머지 가림 |
| `maskAddr` | 주소 | 앞4 유지 | 앞7 유지 | 앞10 유지 |
| `maskCtzNum` | 주민번호 | 전부 `*` | — | 앞6 패턴 + 가림 |

> ⚠️ **Java 와 Python 테스트가 미묘하게 다르다** (예: Java email `HI` 는 `@` 도 가리지만, Python 테스트는 `@` 유지를 요구).
> ➡️ **충돌 시 Python 테스트(`tests/`)를 정본으로 삼는다.** Java 는 *영감/엣지케이스 카탈로그* 로만 활용.
> ➡️ Java 의 가치: ① dash 포맷 보존(전화/카드/주민) ② 길이 경계 처리 ③ "절대 raw 노출 금지" 폴백 철학.

### 2.4 그 외 의도된 모듈
- `patterns.py` — 타입별 **탐지 정규식** (email/phone/name/address/credit_card/ssn/ip 등).
- `veil/meta.py` → `manage_pii_meta(...)` — 탐지·마스킹 **메타/메트릭** (건수, 타입분포, 검증). `tests/test_meta.py` 가 스펙이 될 예정.
- `tests/test_pipeline.py` — **E2E**: 원문 → 탐지 → 마스킹 → 재조립. "모든 PII 가림 + 비‑PII 불변" 검증.

---

## 3. 🔴 P0 — 반드시 먼저 (블로커 해소: "녹색 테스트" 만들기)

### 3.1 [의사결정] 패키지 이름 단일화 ⭐ 최우선
현재 `pyveil/`(디렉터리·배포명) 과 `veil`(테스트 import) 가 분열. **하나를 골라야 한다.**

- **옵션 A (권장) — 배포명 `pyveil`, import 명 `pyveil` 로 통일**
  - WIP 테스트의 `from veil.masker import ...` → `from pyveil.masker import ...` 로 수정.
  - `veil/meta.py` → `pyveil/meta.py` 로 이동. `veil/` 디렉터리 삭제.
  - 장점: `pip install pyveil` → `import pyveil` (관례 일치, 혼란 0). 배포명 이미 본인 소유.
- **옵션 B — 배포명 `pyveil`, import 명 `veil` 유지**
  - `pyveil/` → `veil/` 로 이동, `pyproject` 의 `[tool.setuptools] packages = ["veil"]` + `package-data` 키 수정.
  - 테스트 그대로. 단점: install≠import 라 신규 사용자 혼란, README 에 별도 설명 필요.

> **권장: 옵션 A.** 가장 관례적이고 문서/예제/CLI 전반이 깔끔해진다.
> (이 문서의 이후 경로는 옵션 A 기준 `pyveil.*` 로 표기. 옵션 B 채택 시 `veil.*` 로 치환.)

### 3.2 코어 구현 (테스트 통과가 수용 기준)
- [ ] `pyveil/utils.py` — `mask_string(n)`, `keep_head/keep_tail`, dash 보존 헬퍼 등 공용 유틸 + 완전한 타입힌트.
- [ ] `pyveil/patterns.py` — 타입별 `re.Pattern` 상수 + `detect(text) -> list[span]`. (email/phone/name/address/credit_card 최소, 이후 ssn/ip 확장)
- [ ] `pyveil/masker.py` — `mask_pii(items, level="hi") -> list[dict]`. §2.2 매트릭스 충족. 타입→마스커 디스패치.
- [ ] `pyveil/meta.py` — `manage_pii_meta(...)` (메트릭 집계). `tests/test_meta.py` 채운 뒤 구현.
- [ ] `pyveil/__init__.py` — 공개 API export (`mask_pii`, `detect`, `__version__`, …) + `__all__`. 끝줄 개행(W292) 추가.

### 3.3 패키징/설정 정리
- [ ] **`pyproject.toml addopts`**: `--cov*` 3줄을 `addopts` 에서 제거 → CI 에서만 `pytest --cov` 로 호출.
      (이유: 기본 `pytest` 가 plugin 없는 환경에서 폭사. 개발자 로컬 진입장벽.)
- [ ] **`py.typed`**: `pyveil/py.typed` 빈 파일 생성 (이미 `package-data` 에 선언됨).
- [ ] **ruff 설정 현행화**: `[tool.ruff]` 의 `select/ignore/per-file-ignores` → `[tool.ruff.lint]` 하위로 이동(deprecation 제거).
- [ ] **메타 placeholder 치환**: `your.email@example.com` → 실제, `yourusername` → `hyeonsangjeon` (URL 5곳).
- [ ] **죽은 참조 제거**: `MANIFEST.in` 의 `include CLAUDE.md` 삭제(또는 CLAUDE.md 추가). `a.txt` 삭제. `.DS_Store` 정리.

> ✅ **P0 완료 게이트**: `python3 -m pytest -q` → **all green**, `python3 -c "import pyveil; print(pyveil.mask_pii)"` 동작, `ruff check .` → **0 error/0 warning**.

---

## 4. 🟠 P1 — 핵심 기능 & 품질 (제품이 "동작" 하는 단계)

- [ ] **탐지기 강화** — `patterns.py` 에 신뢰도 높은 정규식. 최소 검증셋: 국제전화(`+`), dash 유무, 카드 4‑4‑4‑4, 한국 주민번호 패턴, IPv4. 오탐/미탐 케이스 테이블화.
- [ ] **파이프라인** — `pyveil/pipeline.py` 또는 `mask_text(text, level)`: 탐지→마스킹→재조립(인덱스 역순 치환으로 offset 안전). `tests/test_pipeline.py` 충족.
- [ ] **레벨 의미 문서화** — `hi/mid/low` 의 "무엇을 남기고 무엇을 가리는가" 를 docstring + README 표로 명문화 (§2.2 재사용).
- [ ] **결정성(determinism)** — 동일 입력 → 동일 출력 보장(랜덤 토큰 쓰면 seed 옵션 제공). PII 도구 신뢰의 핵심.
- [ ] **타입 안전** — 전 공개 함수 타입힌트 + `mypy` 통과(`disallow_untyped_defs` 이미 켜짐).
- [ ] **테스트 커버리지 ≥ 90%** — 타입×레벨 행렬 + 경계(빈문자열/짧은입력/유니코드/한글이름) + property‑based(`hypothesis`) 1~2개.
- [ ] **에러 철학** — 알 수 없는 type/level 시 안전 폴백(절대 raw PII 누출 금지) + 명확한 예외. Java 의 `****` 폴백 사상 계승.
- [ ] **examples/basic_usage.py 실동작화** — `__main__` 가드로 즉시 실행되어 before→after 출력.

---

## 5. 🟡 P2 — Awesome 등급 폴리싱 ("한눈에 WOW")

### 5.1 README (첫인상 = 전부)
- [ ] **히어로**: 한 줄 가치제안 + 1초 demo (asciinema 또는 before/after 코드블록).
- [ ] **배지 풀세트**: PyPI version, Python versions, CI status, codecov, license, downloads, ruff, mypy, pre‑commit.
- [ ] **30초 Quickstart**: 설치 → 5줄 예제 → 출력. 복붙 즉시 동작.
- [ ] **레벨/타입 매트릭스 표**(§2.2) + 실제 마스킹 예시.
- [ ] **비교표**: 유사 라이브러리 대비 차별점(레벨식 마스킹, dash 보존, 타입 다양성, 0 dependency).
- [ ] **"Privacy by design"** 섹션: 테스트/문서에 **실제 PII 0** (현재 WIP 가 잘 지키는 중 — 명시적으로 홍보).
- [ ] README 와 `docs/README.md` 잘린 부분 완성 + `pip install veil` → `pip install pyveil` 오타 수정.

### 5.2 문서 사이트
- [ ] `mkdocs-material` 로 docs 사이트(개념/API/레시피/보안노트). GitHub Pages 자동배포.

### 5.3 CLI (체감 WOW 큼)
- [ ] `pyveil` 콘솔 스크립트: `pyveil mask --level hi --in file.txt` / stdin 파이프. `[project.scripts]` 등록.

### 5.4 커뮤니티 헬스 파일
- [ ] `CHANGELOG.md`(Keep a Changelog), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`(PII 도구라 필수),
      `.github/ISSUE_TEMPLATE/*`, `PULL_REQUEST_TEMPLATE.md`, `CODEOWNERS`.

### 5.5 훅 (pre-commit) — 사용자가 "훅" 명시 요청한 부분 ⭐
`.pre-commit-config.yaml` 도입. 권장 훅:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.2
    hooks: [{id: ruff, args: [--fix]}, {id: ruff-format}]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks: [{id: mypy, additional_dependencies: []}]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - {id: end-of-file-fixer}      # W292 류 재발 방지
      - {id: trailing-whitespace}
      - {id: check-yaml}
      - {id: check-added-large-files}
      - {id: check-merge-conflict}
      - {id: detect-private-key}     # PII 도구에 어울리는 가드
```
- [ ] `black` 채택 여부 결정: `ruff-format` 가 black 호환이므로 **black 제거하고 ruff-format 단일화** 권장(설정 1곳).

### 5.6 CI/CD (GitHub Actions)
- [ ] `.github/workflows/ci.yml`: matrix `py 3.8–3.12` × {lint(ruff), type(mypy), test(pytest --cov)} + codecov 업로드.
- [ ] `release.yml`: 태그 → `python -m build` → **PyPI Trusted Publishing(OIDC)** 게시. (`pyveil` 이미 본인 소유.)
- [ ] (선택) `pre-commit.ci` 또는 CI 내 `pre-commit run --all-files`.

### 5.7 벤치마크/성능
- [ ] 대용량 텍스트 처리량 측정 스크립트 + README 표. 정규식 컴파일 캐싱.

---

## 6. 보안·프라이버시 원칙 (PII 도구의 정체성)
- [ ] **테스트/문서/예제에 실제 PII 절대 금지** — 전부 `dummy`/`example`/`9999…` 합성값. (현재 WIP 가 이미 잘 지킴 → 회귀 방지 위해 `detect-private-key` 훅 + 리뷰 체크리스트.)
- [ ] **비가역성 명시** — 마스킹은 단방향. 가역 토큰화가 필요하면 별도 API 로 분리하고 키 관리 경고.
- [ ] **로케일 인지** — 한국 주민번호/전화 등 KR 특화 패턴은 옵션 플래그로. 오탐 위험 문서화.
- [ ] **"절대 raw 누출 금지" 폴백** — 알 수 없는 입력은 안전하게 전부 가림(Java `****` 사상).

---

## 7. 파일별 액션 체크리스트 (codex 실행용)

| 파일 | 액션 | 수용 기준 |
|---|---|---|
| `pyveil/__init__.py` | 공개 API export, `__all__`, 끝줄 개행 | `import pyveil; pyveil.mask_pii` OK, W292 해소 |
| `pyveil/utils.py` | 마스킹 유틸 구현 + 타입힌트 | `test_utils.py` green |
| `pyveil/patterns.py` | 타입별 정규식 + `detect()` | `test_patterns.py` green |
| `pyveil/masker.py` | `mask_pii(items, level)` 구현 | `test_masker.py` 15케이스 green |
| `pyveil/meta.py` | `manage_pii_meta()` 구현 | `test_meta.py` green |
| `pyveil/pipeline.py` | `mask_text(text, level)` E2E | `test_pipeline.py` green |
| `pyveil/py.typed` | 빈 마커 파일 생성 | mypy 가 타입 인식 |
| `pyproject.toml` | `addopts` cov 제거, ruff `lint.*` 이동, 메타 치환, `[project.scripts]` | `pytest`/`ruff` 무옵션 동작 |
| `MANIFEST.in` | `CLAUDE.md` 참조 제거 | sdist 빌드 경고 0 |
| `README.md`/`docs/README.md` | 완성 + `pip install pyveil` | 잘린 섹션 없음 |
| `examples/basic_usage.py` | 실행 가능한 데모 | `python examples/basic_usage.py` 출력 |
| `.pre-commit-config.yaml` | 신규 | `pre-commit run --all-files` green |
| `.github/workflows/ci.yml` | 신규 | PR 에서 matrix green |
| (정리) `a.txt`, `.DS_Store`, 중복 `veil/` | 삭제 | 트리 클린 |

---

## 8. Definition of Done — 검증 명령어 (codex 가 그대로 실행)
```bash
# 0) 의존성
pip install -e ".[dev]"

# 1) import 동작
python -c "import pyveil; print(pyveil.__version__); print(pyveil.mask_pii)"

# 2) 린트/포맷/타입 (전부 0 error)
ruff check .
ruff format --check .
mypy pyveil

# 3) 테스트 + 커버리지 (≥90%)
pytest --cov=pyveil --cov-report=term-missing

# 4) 훅
pre-commit run --all-files

# 5) 패키지 빌드(경고 0) + 메타데이터 검증
python -m build
twine check dist/*

# 6) 예제 즉시 실행
python examples/basic_usage.py
```
**전부 통과 = Round‑2 완료.**

---

## 9. 다음 라운드 예고 (Round‑3 teaser)
- Presidio/spaCy 등 **NER 기반 탐지** 옵션(정규식 한계 보완).
- **스트리밍/대용량** 처리 + 비동기 API.
- **다국어 로케일 팩**(KR/JP/EU GDPR 프로파일).
- **가역 토큰화(FPE)** 별도 모듈 + 키 관리.
- 커버리지 ≥95%, 벤치마크 회귀 게이트, docs 사이트 정식 런칭.

---

### 부록 A — 우선순위 한 장 요약
```
P0 (블로커)  : 이름통일 → 코어구현 → pytest/py.typed/ruff/메타 정리   ⇒ 녹색 테스트
P1 (기능품질): 탐지강화 · 파이프라인 · 결정성 · mypy · cov≥90 · 폴백
P2 (WOW)     : README/배지 · docs · CLI · 헬스파일 · pre-commit · CI/CD · 벤치마크
보안전반     : 실 PII 0 · 비가역 명시 · 로케일 · raw 누출 금지
```

### 부록 B — 레퍼런스 출처
- Python 계약: `tests/test_masker.py` (정본), `tests/test_pipeline.py`, `tests/test_meta.py`
- 마스킹 영감: `local.data/mask/{MaskFilter,MaskFormat,MaskingRuleMapper,MaskingRuleCDTO}.java`
- 패키징 사실: PyPI `pyveil` 0.1.0 (사용자 본인 게시) — 배포명 유지 결정 근거
