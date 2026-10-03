.text
.p2align 2
.global frame_sv_entry
.hidden frame_sv_entry
.type frame_sv_entry,%function
frame_sv_entry:
    bti jc
    mov x3, x27
    mov x4, x7
    b frame_sv_upload
.size frame_sv_entry, .-frame_sv_entry
.section .note.GNU-stack,"",%progbits
