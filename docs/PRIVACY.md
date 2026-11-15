# Privacy: integrity signals in course tests

Course tests can record a small set of browser signals so an instructor can see, next to
the answers, whether something deserves a conversation. This page describes exactly what
is collected, why, for how long, and how it is deleted. It is written with India's
Digital Personal Data Protection Act 2023 and the DPDP Rules 2025 in mind: collect the
minimum, say clearly what and why, ask before collecting, and delete when no longer
needed.

These are signals, not proctoring. Nothing is decided automatically: no signal changes
a grade or fails a student. The instructor reviews them and decides.

## Consent

Before a test starts, the student sees a notice that lists everything below. The test
cannot start until the student accepts it. Camera checks are a separate, optional
choice: the instructor can turn them off for a test, and a student can decline them and
still take the test.

## What is collected

Only an event log, one row per signal: the kind of signal, the time on the student's
device, how long it lasted, a short detail, and the time the server received it.

| Signal | Recorded when | Detail stored |
|---|---|---|
| `tab_hidden` | The test tab was hidden (another tab or app) | Duration |
| `window_blur` | The browser window lost focus | Duration |
| `fullscreen_exit` | The student left full screen after entering it | – |
| `copy` | Text was copied on the test page | Number of characters, not the text |
| `paste` | Text was pasted on the test page | Number of characters, not the text |
| `no_face` | Camera checks on: no face for more than 5 seconds | Duration |
| `multiple_faces` | Camera checks on: two faces for more than 2 seconds | Duration |
| `head_turned` | Camera checks on: head turned more than 35° for more than 3 seconds | Duration |
| `camera_unavailable` | Camera checks were allowed but could not start | – |

With each answer the platform also stores how long the answer box had focus and how
many characters were pasted into it.

**Never collected:** images, video, audio, screen contents, keystrokes, the copied or
pasted text, or where on the screen the student is looking (gaze tracking is not used:
webcam gaze estimates are too unreliable to be fair).

## How the camera checks work

Face detection runs entirely in the student's browser with MediaPipe Face Landmarker.
The camera picture is analysed on the device and discarded; it is never uploaded or
stored. To run, the browser downloads the detection program (WebAssembly from the
jsDelivr CDN) and the face model (from Google's storage servers). Those downloads are
ordinary file requests and carry no images.

## Who can see it

Only the course's instructor (and platform admins) on the test's results page. Other
students cannot see it. Signals are never sent to a language model.

## Retention and deletion

Integrity events are deleted automatically by a daily job once they are older than
`INTEGRITY_LOG_RETENTION_DAYS` (30 days by default). Deleting a test, a course or a
student account deletes the related events immediately.

Answers, grades and the grade change log are part of the course record and stay until
the test or course is deleted.

## Language models in tests

Some features send text to a language model provider (Groq or Gemini, see
[AI_FEATURES.md](AI_FEATURES.md)): the student's answers and their own submitted code
for grading against the rubric, for the follow-up question, and for viva questions.
Integrity signals, email addresses and other students' data are not sent, except that
the optional similarity second opinion sends the code of the two submissions an
instructor asks about.
