---
name: paste-loop
description: Hand Tee a command or Colab cell to run on his own device, then judge the output he pastes back. Use whenever a step can only run on his machine (his Colab, his Drive, his laptop, his phone) and whenever a message of his is mostly pasted terminal or notebook output. One step per message, one copy block, the exact line that means success, and a pass or fail verdict first on whatever comes back.
---

# The paste loop

Tee works mostly from an iPhone. When a step has to run on his side, the loop is
command out, output pasted back, verdict. In the 2026-10-14 read of every cloud session, a text match
counted 33 pasted outputs (17 after 10-11) and 13 asks for the command by itself
or in smaller parts. Those are match counts, not a hand count. His words, each one a failure
of an earlier reply: "you do too much talking just give me the command for 10
tools the other words are just padding so stop it", "Make the command smaller
commands", "You have to spilt the script in smaller parts and send one at a
time", "Give me command by itself to copy and paste", "i don't own a Mac so make
it work".

## Before handing anything over

1. Run it yourself if you can. The loop is for steps only he can run: his Colab,
   his Drive, his laptop. Anything the container can execute and read back is
   executed here and reported, not delegated.
2. Assume iPhone, no terminal, no Mac. He has also worked from a Linux terminal
   and a laptop, so if he has said laptop in this session, he is on the laptop
   until he says otherwise. If the step needs a terminal and
   he is on the phone, route it through a Colab cell, not through a terminal
   lesson.
3. Decide the success line first. You cannot run a notebook cell, so you cannot
   know what a library prints. Write the command to end with a marker you
   control, such as `print("STEP 2 OK")`, and make that marker the success line.

## The message that hands over a step

- One message, one fenced block holding only the command or cell, nothing in the
  block that is not meant to be run.
- Short enough to paste from a phone: about 15 lines at most. A longer script is
  split into numbered parts, each self-contained, one part per message.
- Directly under the block, one line: `Success looks like: <the exact line>`.
  Add `A failure ends in: <what the last line looks like>` only when the failure
  is predictable.
- No tour of what the command does. If it writes, deletes or sends anything, say
  that in one sentence above the block.
- When a step needs a link, give the full URL, plain, in the same message.

## The message that judges what he pastes

- First sentence is `Pass:` or `Fail:`, measured against the success line you
  gave, not against a new reading of the output. A Fail names the cause in that
  same sentence. Then the next block, or the fix. Nothing before the verdict.
- A paste that matches no success line you gave (a log from somewhere else, a
  command someone else wrote) gets no verdict. Say what it is and ask which
  step it belongs to.
- Read the last traceback line and the line that names the file or cell. A
  notebook paste carries earlier noise, and Colab's own text on a Drive mount
  that is already in place says how to force a remount, so that line is
  information and not the failure.
- The same error twice means the command was wrong, not unlucky. Change one
  thing, say which, and do not resend the identical block.
- A pass on the output proves the process ran. A render, a voice file or a
  video is not shipped until he has watched or listened to it end to end; say
  so instead of calling the artifact done.
- If no output comes back, the step is unverified. Say that. Do not carry on as
  if it passed.

## Secrets

Commands print lengths, status codes and booleans, never the secret. Read a
secret with `read -rs` or a Colab secret, and print `${#TOKEN}` or the HTTP
status. A paste of his from 2026-08-30 reads "stored key length: 267", which is
the pattern to copy. If his
paste contains a token, key or code anyway, do not quote or echo it, say once
that it needs rotating, and carry on with the rest of the output.

## Not for

Deciding what to build, ruling on options (those go on an inline card), or
steps the container can run. Those are not this loop.
