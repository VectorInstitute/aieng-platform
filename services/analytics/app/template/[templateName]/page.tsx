import { getSession } from '@/lib/session';
import { redirect } from 'next/navigation';
import TemplateTeamsContent from './template-teams-content';

export default async function TemplateTeamsPage({ params }: { params: { templateName: string } }) {
  const session = await getSession();

  if (!session.user) {
    redirect('/analytics/login');
  }

  return <TemplateTeamsContent user={session.user} templateName={params.templateName} />;
}
