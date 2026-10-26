import { callServerTool, parseWeeklyCalendarData, sendUserMessage } from "../bridge.ts";
import type { ConnectedView } from "../bridge.ts";
import { mountMcpView } from "../mcpView.tsx";
import { WeeklyCalendarPage } from "../pages";
import type { WeeklyCalendarActions } from "../pages";
import type { WeeklyCalendarData } from "../types.ts";

/**
 * Refresh re-runs show_weekly_calendar directly and re-renders in place.
 * optimize_plan / rebalance_plan only return unsaved proposals, so those
 * buttons ask the model to run them and decide what to persist.
 */
function calendarActions({
  app,
  data,
  host,
  applyResult,
}: ConnectedView<WeeklyCalendarData>): WeeklyCalendarActions {
  const { plan_id, member_id } = data;
  const plan = `my meal plan "${data.plan_summary.plan_name}" (plan_id ${plan_id})`;

  const refresh = async () => {
    const args = member_id ? { plan_id, member_id } : { plan_id };
    applyResult(await callServerTool(app, "show_weekly_calendar", args));
  };

  const optimizeEmptySlots = () =>
    sendUserMessage(
      app,
      `Please fill the empty slots in ${plan} using optimize_plan` +
        (member_id ? ` for member_id ${member_id}` : " for my family members") +
        ", and show me the proposal before adding anything to the plan.",
    );

  const rebalance = () =>
    sendUserMessage(
      app,
      `Please rebalance ${plan} for member_id ${member_id ?? "(none)"} using rebalance_plan, ` +
        "and show me the proposed changes before applying anything.",
    );

  return {
    refresh: host.serverTools ? refresh : undefined,
    optimizeEmptySlots: host.message ? optimizeEmptySlots : undefined,
    rebalance: host.message ? rebalance : undefined,
  };
}

mountMcpView({
  appName: "Weekly Calendar",
  parse: parseWeeklyCalendarData,
  displayModes: ["inline", "fullscreen"],
  render: (view) => (
    <WeeklyCalendarPage
      source={{
        loading: false,
        data: view.data,
        actions: calendarActions(view),
        display: view.display,
      }}
    />
  ),
});
