import { useEffect } from "react";
import { api } from "../lib/api";
import { clearCache, invalidate, useQuery } from "../lib/query";
import { useRoute } from "../lib/router";
import type { Profile } from "../lib/types";
import { Shell } from "../components/Shell";
import { ErrorState, Skeleton, Toaster } from "../components/feedback";
import { AuthPage } from "../pages/AuthPage";
import { CommandCenter } from "../pages/CommandCenter";
import { QuestBoard } from "../pages/QuestBoard";
import { HabitsPage } from "../pages/HabitsPage";
import { SkillsPage } from "../pages/SkillsPage";
import { AnalyticsPage } from "../pages/AnalyticsPage";
import { AchievementsPage } from "../pages/AchievementsPage";
import { SettingsPage } from "../pages/SettingsPage";

export function App() {
  const me = useQuery("profile", () => api.get<Profile>("/profile"));
  const route = useRoute();

  useEffect(() => {
    document.documentElement.dataset.theme = me.data?.theme ?? "obsidian";
  }, [me.data?.theme]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [route.page]);

  const signedIn = () => {
    clearCache();
    window.location.hash = "#/";
  };

  if (me.error?.status === 401) {
    return (
      <>
        <AuthPage onSignedIn={signedIn} />
        <Toaster />
      </>
    );
  }
  if (me.error) return <div className="p-6"><ErrorState error={me.error} onRetry={() => invalidate("profile")} /></div>;
  if (!me.data) return <div className="p-6 max-w-[900px] mx-auto"><Skeleton lines={5} /></div>;

  const p = me.data;
  const today = p.today;
  let page;
  switch (route.page) {
    case "quests": page = <QuestBoard today={today} />; break;
    case "habits": page = <HabitsPage />; break;
    case "skills": page = <SkillsPage skillId={route.skillId} />; break;
    case "analytics": page = <AnalyticsPage today={today} />; break;
    case "achievements": page = <AchievementsPage />; break;
    case "settings": page = <SettingsPage onSignedOut={() => { clearCache(); window.location.hash = "#/"; }} />; break;
    default: page = <CommandCenter />;
  }
  return (
    <>
      <Shell route={route} name={p.display_name} avatar={p.avatar} level={p.progress.level}>{page}</Shell>
      <Toaster />
    </>
  );
}
