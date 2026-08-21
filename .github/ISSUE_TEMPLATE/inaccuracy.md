---
name: Something here is wrong
about: A query, entity name, verb signature, or explanation that does not match reality
title: ''
labels: accuracy
---

**What the documentation says**

<!-- Quote it, with the file and line. -->

**What your server says**

<!-- The query you ran and what came back. These are usually the useful ones:

    SELECT FullName FROM Metadata.Entity WHERE FullName LIKE '%Something%'

    SELECT Name, Type, IsKey FROM Metadata.Property
    WHERE Entity.FullName = 'Orion.Nodes'

    SELECT Position, Name, Type, IsOptional FROM Metadata.VerbArgument
    WHERE EntityName = 'Orion.Nodes' AND VerbName = 'Unmanage' ORDER BY Position
-->

**Your platform version**

<!-- This repository documents 2026.2. The schema changes between releases and also
depends on which modules are licensed and installed, so a difference may be a version
difference rather than an error. Find yours in the web console, or:

    SELECT ServerName, EngineVersion, PackageName FROM Orion.Engines
-->

**Anything else**

<!-- If the difference is a version difference, say so: a note in the page about when
the behaviour changed is often more useful than a correction. -->
