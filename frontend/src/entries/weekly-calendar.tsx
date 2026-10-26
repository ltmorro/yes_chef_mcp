import { callTool, parseWeeklyCalendarData } from "../bridge.ts";
import { mountMcpView } from "../mcpView.tsx";
import { WeeklyCalendarPage } from "../pages";

mountMcpView({
  appName: "Weekly Calendar",
  parse: parseWeeklyCalendarData,
  render: (app, data) => (
    <WeeklyCalendarPage
      source={{
        loading: false,
        data,
        // These calls don't match the server's tools yet (optimize_empty_slots and
        // refresh_plan don't exist; rebalance_plan needs member_id) — fixed in a follow-up PR
        actions: {
          optimizeEmptySlots: (planId) =>
            callTool(app, "optimize_empty_slots", { plan_id: planId }),
          rebalance: (planId) => callTool(app, "rebalance_plan", { plan_id: planId }),
          refresh: (planId) => callTool(app, "refresh_plan", { plan_id: planId }),
        },
      }}
    />
  ),
});
