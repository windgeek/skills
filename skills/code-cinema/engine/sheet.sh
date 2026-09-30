# bash sheet.sh out.jpg t1 t2 ...  把 build/still_*.jpg 拼成两列检查图
out=$1; shift
cd "$(dirname "$0")/build"
inputs=(); for t in "$@"; do inputs+=(-i "still_${t/./_}.jpg"); done
n=$#
ffmpeg -y -loglevel error -nostdin "${inputs[@]}" -filter_complex "$(for i in $(seq 0 $((n-1))); do printf "[$i]scale=960:540[s$i];"; done; for i in $(seq 0 $((n-1))); do printf "[s$i]"; done; printf "xstack=inputs=$n:layout="; for i in $(seq 0 $((n-1))); do c=$((i%2)); r=$((i/2)); printf "%s_%s" $((c*960)) $((r*540)); [ $i -lt $((n-1)) ] && printf "|"; done)" "$out"
echo "$(pwd)/$out"
