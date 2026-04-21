import { getSession } from '@/lib/session';
import { redirect } from 'next/navigation';
import TemplateTeamsContent from './template-teams-content';

export default async function TemplateTeamsPage({ params }: { params: Promise<{ templateName: string }> }) {
  const session = await getSession();
  const { templateName } = await params;

  if (!session.user) {
    redirect('/analytics/login');
  }

  return <TemplateTeamsContent user={session.user} templateName={templateName} />;
}
