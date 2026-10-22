import { redirect } from "next/navigation";

export default function ControlPage() {
  redirect("/command-center?view=control");
}
