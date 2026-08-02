import ProjectClient from "./client";

export function generateStaticParams() {
  return [{ id: "1" }];
}

export default function ProjectPage({ params }: { params: { id: string } }) {
  return <ProjectClient id={params.id} />;
}
