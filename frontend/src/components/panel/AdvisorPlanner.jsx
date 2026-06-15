// Deep-analysis water planner for one district: pick a goal -> answer a few
// short model-generated questions -> get a structured report. No open chat.
// State is component-local and resets when the panel switches district (parent
// keys this by district name).
import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { fetchAdvisorQuestions, fetchAdvisorReport } from '../../api/client.js';
import {
  useDistrictForecast,
  useDistrictHistory,
  useDistrictPermeability,
  useDistrictSatellite,
} from '../../api/hooks.js';
import { ADVISOR_NEEDS, buildSnapshot, needLabel } from '../../lib/advisor.js';
import ReportView from './ReportView.jsx';

export default function AdvisorPlanner({ district }) {
  // Build the data snapshot from the (already-cached) district queries, so the
  // popout only needs the district name.
  const history = useDistrictHistory(district);
  const forecast = useDistrictForecast(district);
  const satellite = useDistrictSatellite(district);
  const permeability = useDistrictPermeability(district);
  const snapshot = useMemo(
    () =>
      buildSnapshot({
        monthly: history.data?.monthly,
        forecast: forecast.data?.forecast,
        satellite: satellite.data?.observations,
        permeability: permeability.data,
      }),
    [history.data, forecast.data, satellite.data, permeability.data],
  );

  const [need, setNeed] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({}); // keyed by question id
  const [report, setReport] = useState(null);

  const questionsM = useMutation({
    mutationFn: (needId) =>
      fetchAdvisorQuestions({ districtName: district, need: needId, snapshot }),
    onSuccess: (data) => {
      setQuestions(data.questions ?? []);
      setAnswers({});
    },
  });

  const reportM = useMutation({
    mutationFn: () =>
      fetchAdvisorReport({
        districtName: district,
        need,
        snapshot,
        answers: questions
          .map((q) => ({ question: q.question, answer: (answers[q.id] ?? '').trim() }))
          .filter((a) => a.answer),
      }),
    onSuccess: (data) => setReport(data.report),
  });

  function pickNeed(needId) {
    setNeed(needId);
    setReport(null);
    questionsM.mutate(needId);
  }

  function reset() {
    setNeed(null);
    setQuestions([]);
    setAnswers({});
    setReport(null);
    questionsM.reset();
    reportM.reset();
  }

  // Step: goal picker
  if (!need) return <NeedPicker district={district} onPick={pickNeed} />;

  // Step: finished report
  if (report) {
    return (
      <div className="space-y-2">
        <ReportView report={report} need={need} district={district} />
        <button
          type="button"
          onClick={reset}
          className="text-xs font-semibold text-ink-soft underline-offset-2 hover:text-ink hover:underline"
        >
          ← Start a new plan
        </button>
      </div>
    );
  }

  // Step: questions (loading / form / generating report)
  return (
    <div className="rounded-lg border border-ink/10 bg-paper/60 p-4">
      <p className="text-sm font-semibold">
        {needLabel(need)} · {district}
      </p>

      {questionsM.isPending && (
        <p className="mt-2 text-xs italic text-ink-soft">Preparing a few questions…</p>
      )}
      {questionsM.isError && (
        <ErrorRetry error={questionsM.error} onRetry={() => questionsM.mutate(need)} />
      )}

      {questions.length > 0 && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (!reportM.isPending) reportM.mutate();
          }}
          className="mt-3 space-y-3"
        >
          {questions.map((q) => (
            <div key={q.id}>
              <label htmlFor={`adv-${q.id}`} className="block text-sm font-medium">
                {q.question}
              </label>
              <input
                id={`adv-${q.id}`}
                value={answers[q.id] ?? ''}
                placeholder={q.hint || ''}
                disabled={reportM.isPending}
                onChange={(event) =>
                  setAnswers((prev) => ({ ...prev, [q.id]: event.target.value }))
                }
                className="mt-1 w-full rounded-lg border border-ink/15 bg-surface px-3 py-2 text-sm focus-visible:outline-water disabled:opacity-50"
              />
            </div>
          ))}

          {reportM.isError && <ErrorRetry error={reportM.error} inline />}

          <div className="flex items-center gap-3">
            <button type="submit" disabled={reportM.isPending} className="btn-primary !py-2 text-sm">
              {reportM.isPending ? 'Analyzing…' : 'Generate report'}
            </button>
            <button
              type="button"
              onClick={reset}
              className="text-xs font-semibold text-ink-soft hover:text-ink"
            >
              Cancel
            </button>
          </div>
          <p className="text-xs text-ink-soft">Answer what you can — leave blanks if unsure.</p>
        </form>
      )}
    </div>
  );
}

function NeedPicker({ district, onPick }) {
  return (
    <div className="rounded-lg border border-ink/10 bg-paper/60 p-4">
      <p className="text-sm font-semibold">Plan your water use with AI</p>
      <p className="mt-1 text-xs text-ink-soft">
        Pick a goal. The advisor reviews {district}'s risk, forecast, and recharge data, asks a
        few short questions, then writes a deep-analysis report.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {ADVISOR_NEEDS.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => onPick(option.id)}
            className="rounded-lg border border-ink/15 bg-surface px-3 py-2.5 text-left transition-colors hover:border-water hover:bg-water/5 focus-visible:outline-water"
          >
            <span className="block text-sm font-semibold">{option.label}</span>
            <span className="mt-0.5 block text-xs text-ink-soft">{option.blurb}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ErrorRetry({ error, onRetry, inline = false }) {
  const busy = error?.response?.status === 429;
  const message = busy
    ? 'The advisor is busy right now (high demand). Wait a moment and try again.'
    : 'The advisor is unavailable right now. Please try again.';
  return (
    <div className={inline ? '' : 'mt-2'}>
      <p role="alert" className="text-xs font-medium text-risk-critical">
        {message}
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 text-xs font-semibold text-water hover:underline"
        >
          Retry
        </button>
      )}
    </div>
  );
}
